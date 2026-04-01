package ai.bistelligence.chat_backend_spring.domain.auth.controller;

import ai.bistelligence.chat_backend_spring.auth.dto.TokenResponse;
import ai.bistelligence.chat_backend_spring.common.api.Api;
import ai.bistelligence.chat_backend_spring.domain.auth.dto.LoginRequest;
import ai.bistelligence.chat_backend_spring.domain.auth.dto.SignupRequest;
import ai.bistelligence.chat_backend_spring.domain.auth.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/open-api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/signup")
    public Api<String> signup(@Valid @RequestBody SignupRequest request) {
        authService.signup(request);
        return Api.OK("회원가입이 완료되었습니다");
    }

    @PostMapping("/login")
    public Api<TokenResponse> login(@Valid @RequestBody LoginRequest request) {
        return Api.OK(authService.login(request));
    }

    @PostMapping("/refresh")
    public Api<TokenResponse> refresh(@RequestHeader("refresh-token") String refreshToken) {
        return Api.OK(authService.refreshToken(refreshToken));
    }
}
