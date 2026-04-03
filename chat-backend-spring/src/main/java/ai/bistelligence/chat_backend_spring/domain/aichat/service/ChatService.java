package ai.bistelligence.chat_backend_spring.domain.aichat.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.bsc.langgraph4j.CompiledGraph;
import org.bsc.langgraph4j.RunnableConfig;
import org.bsc.langgraph4j.prebuilt.MessagesState;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.Optional;

@Slf4j
@Service
@RequiredArgsConstructor
public class ChatService {

    private final CompiledGraph<MessagesState<Message>> compiledGraph;

    public String chat(String message, String threadId) {
        UserMessage userMessage = new UserMessage(message);

        Map<String, Object> input = Map.of("messages", List.of(userMessage));

        RunnableConfig config = RunnableConfig.builder()
                .threadId(threadId)
                .build();

        Optional<MessagesState<Message>> result;
        try {
            result = compiledGraph.invoke(input, config);
        } catch (Exception e) {
            log.error("Chat failed for threadId={}", threadId, e);
            throw new RuntimeException("모델 호출 중 오류가 발생했습니다.", e);
        }

        Optional<String> responseText = result
                .flatMap(MessagesState::lastMessage)
                .filter(msg -> msg instanceof AssistantMessage)
                .map(msg -> ((AssistantMessage) msg).getText());

        if (responseText.isEmpty()) {
            log.warn("No assistant response for threadId={}", threadId);
        }

        return responseText.orElse("응답을 생성할 수 없습니다.");
    }
}
