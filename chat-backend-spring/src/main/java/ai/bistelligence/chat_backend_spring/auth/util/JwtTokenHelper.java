package ai.bistelligence.chat_backend_spring.auth.util;

import ai.bistelligence.chat_backend_spring.auth.dto.TokenDto;
import ai.bistelligence.chat_backend_spring.common.error.TokenErrorCode;
import ai.bistelligence.chat_backend_spring.common.exception.ApiException;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

@Component
public class JwtTokenHelper implements TokenHelperIfs {

    @Value("${token.secret.key}")
    private String secretKey;

    @Value("${token.access-token.plus-hour}")
    private Long accessTokenPlusHour;

    @Value("${token.refresh-token.plus-hour}")
    private Long refreshTokenPlusHour;

    @Override
    public TokenDto issueAccessToken(Map<String, Object> data) {
        var expiredLocalDateTime = LocalDateTime.now().plusHours(accessTokenPlusHour);
        var expiredAt = Date.from(expiredLocalDateTime.atZone(ZoneId.systemDefault()).toInstant());

        var key = getSigningKey();
        var token = Jwts.builder()
                .claims(data)
                .signWith(key)
                .expiration(expiredAt)
                .compact();

        return TokenDto.builder()
                .token(token)
                .expiredAt(expiredLocalDateTime)
                .build();
    }

    @Override
    public TokenDto issueRefreshToken(Map<String, Object> data) {
        var expiredLocalDateTime = LocalDateTime.now().plusHours(refreshTokenPlusHour);
        var expiredAt = Date.from(expiredLocalDateTime.atZone(ZoneId.systemDefault()).toInstant());

        var key = getSigningKey();
        var token = Jwts.builder()
                .claims(data)
                .signWith(key)
                .expiration(expiredAt)
                .compact();

        return TokenDto.builder()
                .token(token)
                .expiredAt(expiredLocalDateTime)
                .build();
    }

    @Override
    public Map<String, Object> validationTokenWithThrow(String token) {
        var key = getSigningKey();

        var parser = Jwts.parser()
                .verifyWith(key)
                .build();

        try {
            var claims = parser.parseSignedClaims(token).getPayload();
            return new HashMap<>(claims);
        } catch (ExpiredJwtException e) {
            throw e;
        } catch (Exception e) {
            throw new ApiException(TokenErrorCode.INVALID_TOKEN, e);
        }
    }

    private SecretKey getSigningKey() {
        return Keys.hmacShaKeyFor(secretKey.getBytes());
    }
}
