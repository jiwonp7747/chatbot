package ai.bistelligence.chat_backend_spring.domain.aichat.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class ChatResponse {

    private String answer;
    private String threadId;
}
