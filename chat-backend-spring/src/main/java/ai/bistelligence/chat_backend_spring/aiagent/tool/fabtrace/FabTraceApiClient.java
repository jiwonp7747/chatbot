package ai.bistelligence.chat_backend_spring.aiagent.tool.fabtrace;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.LinkedHashMap;
import java.util.Map;

@Slf4j
@Service
public class FabTraceApiClient {

    private final RestClient restClient;

    public FabTraceApiClient(@Value("${fabtrace.api.url:http://localhost:9090}") String baseUrl) {
        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .build();
    }

    /**
     * GET 요청을 보내고 응답 본문을 문자열로 반환한다.
     *
     * @param path        API 경로 (예: "/api/v1/lots")
     * @param queryParams 쿼리 파라미터 (null 값은 무시됨)
     * @return 응답 본문 문자열, 실패 시 에러 JSON
     */
    public String get(String path, Map<String, Object> queryParams) {
        try {
            UriComponentsBuilder uriBuilder = UriComponentsBuilder.fromPath(path);

            if (queryParams != null) {
                queryParams.forEach((key, value) -> {
                    if (value != null) {
                        uriBuilder.queryParam(key, value);
                    }
                });
            }

            String uri = uriBuilder.build().toUriString();

            return restClient.get()
                    .uri(uri)
                    .retrieve()
                    .body(String.class);
        } catch (Exception e) {
            log.error("Fab Trace API 호출 실패: path={}, params={}", path, queryParams, e);
            return "{\"error\": \"API 호출 실패: " + e.getMessage() + "\"}";
        }
    }

    /**
     * 키-값 쌍으로 파라미터 맵을 생성하는 헬퍼 메서드.
     * null 값은 자동으로 제외된다.
     *
     * <pre>
     * params("start", start, "end", end, "limit", 100)
     * </pre>
     *
     * @param keyValues 키(String)와 값(Object)의 교대 배열
     * @return null 값이 제외된 LinkedHashMap
     */
    public static Map<String, Object> params(Object... keyValues) {
        Map<String, Object> map = new LinkedHashMap<>();
        for (int i = 0; i < keyValues.length - 1; i += 2) {
            String key = String.valueOf(keyValues[i]);
            Object value = keyValues[i + 1];
            if (value != null) {
                map.put(key, value);
            }
        }
        return map;
    }
}
