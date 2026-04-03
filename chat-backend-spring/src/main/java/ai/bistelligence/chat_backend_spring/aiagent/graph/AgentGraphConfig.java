package ai.bistelligence.chat_backend_spring.aiagent.graph;

import lombok.extern.slf4j.Slf4j;
import org.bsc.langgraph4j.CompiledGraph;
import org.bsc.langgraph4j.CompileConfig;
import org.bsc.langgraph4j.StateGraph;
import org.bsc.langgraph4j.agent.AgentEx;
import org.bsc.langgraph4j.checkpoint.MemorySaver;
import org.bsc.langgraph4j.prebuilt.MessagesState;
import org.bsc.langgraph4j.spring.ai.serializer.std.SpringAIStateSerializer;
import org.bsc.langgraph4j.spring.ai.tool.SpringAIToolService;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.ChatOptions;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.ai.support.ToolCallbacks;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import ai.bistelligence.chat_backend_spring.aiagent.tool.datetime.DateTimeTools;
import ai.bistelligence.chat_backend_spring.aiagent.tool.fabtrace.FabTraceTools;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

@Slf4j
@Configuration
public class AgentGraphConfig {

    /**
     * @Tool 메서드를 ToolCallback 리스트로 변환
     */
    @Bean
    public List<ToolCallback> toolCallbacks(FabTraceTools fabTraceTools, DateTimeTools dateTimeTools) {
        return Arrays.asList(ToolCallbacks.from(fabTraceTools, dateTimeTools));
    }

    /**
     * Spring AI 도구를 LangGraph4j에서 실행할 수 있는 서비스
     */
    @Bean
    public SpringAIToolService toolService(List<ToolCallback> toolCallbacks) {
        return new SpringAIToolService(toolCallbacks);
    }

    /**
     * AgentEx 기반 그래프 빌드 및 컴파일
     */
    @Bean
    public CompiledGraph<MessagesState<Message>> compiledGraph(
            OpenAiChatModel chatModel,
            SpringAIToolService toolService,
            List<ToolCallback> toolCallbacks
    ) throws Exception {

        // 도구 정의를 ChatOptions에 바인딩
        ChatOptions chatOptions = OpenAiChatOptions.builder()
                .toolCallbacks(toolCallbacks)
                .internalToolExecutionEnabled(false)
                .build();

        // LLM 호출 액션
        var callModelAction = new org.bsc.langgraph4j.action.AsyncNodeActionWithConfig<MessagesState<Message>>() {
            @Override
            public CompletableFuture<Map<String, Object>> apply(MessagesState<Message> state, org.bsc.langgraph4j.RunnableConfig config) {
                return CompletableFuture.supplyAsync(() -> {
                    log.debug("[AGENT] LLM 호출 - 메시지 수: {}", state.messages().size());

                    Prompt prompt = new Prompt(state.messages(), chatOptions);
                    ChatResponse response = chatModel.call(prompt);
                    AssistantMessage assistant = response.getResult().getOutput();

                    log.debug("[AGENT] LLM 응답 - toolCalls: {}",
                            assistant.getToolCalls() != null ? assistant.getToolCalls().size() : 0);

                    return Map.of("messages", List.of((Message) assistant));
                });
            }
        };

        // 도구 실행 팩토리 (도구명 → 실행 액션)
        java.util.function.Function<String, org.bsc.langgraph4j.action.AsyncNodeActionWithConfig<MessagesState<Message>>> executeToolFactory =
                (toolName) -> (state, config) -> {
                    log.debug("[AGENT] 도구 실행: {}", toolName);

                    Message lastMsg = state.lastMessage().orElseThrow();
                    AssistantMessage assistantMsg = (AssistantMessage) lastMsg;

                    List<AssistantMessage.ToolCall> calls = assistantMsg.getToolCalls().stream()
                            .filter(tc -> tc.name().equals(toolName))
                            .toList();

                    return toolService.executeFunctions(calls, state.data())
                            .thenApply(command -> command.update());
                };

        // 그래프 빌드
        StateGraph<MessagesState<Message>> graph = AgentEx
                .<Message, MessagesState<Message>, ToolCallback>builder()
                .stateSerializer(new SpringAIStateSerializer<>(MessagesState::new))
                .callModelAction(callModelAction)
                .executeToolFactory(executeToolFactory)
                .toolName(tc -> tc.getToolDefinition().name())
                .build(toolService.agentFunctionsCallback(), Map.of());

        // 컴파일 (메모리 체크포인트)
        return graph.compile(
                CompileConfig.builder()
                        .checkpointSaver(new MemorySaver())
                        .build()
        );
    }
}
