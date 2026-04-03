package ai.bistelligence.chat_backend_spring.domain.aichat.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class ChatRequest {

    @NotBlank
    private String message;

    @Size(max = 36)
    @Pattern(regexp = "^[0-9a-fA-F-]{36}$")
    private String threadId;
}
