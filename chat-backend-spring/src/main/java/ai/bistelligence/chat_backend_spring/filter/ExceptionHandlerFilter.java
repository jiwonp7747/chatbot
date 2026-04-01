package ai.bistelligence.chat_backend_spring.filter;

import ai.bistelligence.chat_backend_spring.common.api.Api;
import ai.bistelligence.chat_backend_spring.common.error.ErrorCode;
import ai.bistelligence.chat_backend_spring.common.error.TokenErrorCode;
import ai.bistelligence.chat_backend_spring.common.exception.AuthException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Slf4j
@Component
public class ExceptionHandlerFilter extends OncePerRequestFilter {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        try {
            filterChain.doFilter(request, response);
        } catch (ExpiredJwtException e) {
            log.error("[ExpiredJwtException]", e);
            writeErrorResponse(response, TokenErrorCode.EXPIRED_TOKEN);
        } catch (JwtException | IllegalArgumentException e) {
            log.error("[JwtException]", e);
            writeErrorResponse(response, TokenErrorCode.INVALID_TOKEN);
        } catch (AuthException e) {
            log.error("[AuthException]", e);
            writeErrorResponse(response, e.getErrorCodeIfs(), e.getErrorDescription());
        }
    }

    private void writeErrorResponse(HttpServletResponse response, ai.bistelligence.chat_backend_spring.common.error.ErrorCodeIfs errorCode) throws IOException {
        writeErrorResponse(response, errorCode, errorCode.getDescription());
    }

    private void writeErrorResponse(HttpServletResponse response,
                                    ai.bistelligence.chat_backend_spring.common.error.ErrorCodeIfs errorCode,
                                    String description) throws IOException {
        response.setStatus(errorCode.getHttpStatusCode());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");
        response.getWriter().write(
                objectMapper.writeValueAsString(Api.ERROR(errorCode, description))
        );
    }
}
