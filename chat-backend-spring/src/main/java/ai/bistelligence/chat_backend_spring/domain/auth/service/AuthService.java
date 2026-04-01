package ai.bistelligence.chat_backend_spring.domain.auth.service;

import ai.bistelligence.chat_backend_spring.auth.dto.TokenResponse;
import ai.bistelligence.chat_backend_spring.auth.util.TokenHelperIfs;
import ai.bistelligence.chat_backend_spring.common.exception.ApiException;
import ai.bistelligence.chat_backend_spring.domain.auth.dto.LoginRequest;
import ai.bistelligence.chat_backend_spring.domain.auth.dto.SignupRequest;
import ai.bistelligence.chat_backend_spring.domain.user.entity.User;
import ai.bistelligence.chat_backend_spring.domain.user.error.UserErrorCode;
import ai.bistelligence.chat_backend_spring.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final TokenHelperIfs tokenHelper;
    private final PasswordEncoder passwordEncoder;

    @Transactional
    public void signup(SignupRequest request) {
        if (userRepository.existsById(request.getUserId())) {
            throw new ApiException(UserErrorCode.DUPLICATE_USER_ID);
        }

        var user = User.builder()
                .userId(request.getUserId())
                .password(passwordEncoder.encode(request.getPassword()))
                .name(request.getName())
                .build();

        userRepository.save(user);
    }

    @Transactional(readOnly = true)
    public TokenResponse login(LoginRequest request) {
        var user = userRepository.findById(request.getUserId())
                .orElseThrow(() -> new ApiException(UserErrorCode.USER_NOT_FOUND));

        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new ApiException(UserErrorCode.INVALID_PASSWORD);
        }

        if (!"ACTIVE".equals(user.getStatus())) {
            throw new ApiException(UserErrorCode.INACTIVE_USER);
        }

        return issueToken(user);
    }

    public TokenResponse refreshToken(String refreshToken) {
        var claims = tokenHelper.validationTokenWithThrow(refreshToken);
        var userId = claims.get("userId").toString();

        var user = userRepository.findById(userId)
                .orElseThrow(() -> new ApiException(UserErrorCode.USER_NOT_FOUND));

        return issueToken(user);
    }

    private TokenResponse issueToken(User user) {
        var data = Map.<String, Object>of("userId", user.getUserId());

        var accessToken = tokenHelper.issueAccessToken(data);
        var refreshToken = tokenHelper.issueRefreshToken(data);

        return TokenResponse.builder()
                .accessToken(accessToken.getToken())
                .accessTokenExpiredAt(accessToken.getExpiredAt())
                .refreshToken(refreshToken.getToken())
                .refreshTokenExpiredAt(refreshToken.getExpiredAt())
                .build();
    }
}
