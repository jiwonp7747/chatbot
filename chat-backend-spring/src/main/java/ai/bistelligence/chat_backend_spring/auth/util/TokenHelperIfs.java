package ai.bistelligence.chat_backend_spring.auth.util;

import ai.bistelligence.chat_backend_spring.auth.dto.TokenDto;

import java.util.Map;

public interface TokenHelperIfs {
    TokenDto issueAccessToken(Map<String, Object> data);
    TokenDto issueRefreshToken(Map<String, Object> data);
    Map<String, Object> validationTokenWithThrow(String token);
}
