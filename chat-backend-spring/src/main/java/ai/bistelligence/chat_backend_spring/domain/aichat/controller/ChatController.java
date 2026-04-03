package ai.bistelligence.chat_backend_spring.domain.aichat.controller;

import ai.bistelligence.chat_backend_spring.common.api.Api;
import ai.bistelligence.chat_backend_spring.domain.aichat.dto.ChatRequest;
import ai.bistelligence.chat_backend_spring.domain.aichat.dto.ChatResponse;
import ai.bistelligence.chat_backend_spring.domain.aichat.service.ChatService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/open-api/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;

    @PostMapping
    public Api<ChatResponse> chat(@Valid @RequestBody ChatRequest request) {
        String threadId = StringUtils.hasText(request.getThreadId())
                ? request.getThreadId()
                : java.util.UUID.randomUUID().toString();
        String answer = chatService.chat(request.getMessage(), threadId);
        return Api.OK(new ChatResponse(answer, threadId));
    }
}
