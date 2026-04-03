package ai.bistelligence.chat_backend_spring.aiagent.tool.datetime;

import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

@Component
public class DateTimeTools {

    @Tool(description = "현재 날짜와 시간을 조회합니다.")
    public String getCurrentDateTime() {
        return LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
    }

    @Tool(description = "특정 지역의 타임존을 조회합니다.")
    public String getTimezone(
            @ToolParam(description = "지역명 (예: Asia/Seoul, America/New_York, Europe/London)") String location) {
        try {
            ZoneId zone = ZoneId.of(location);
            LocalDateTime now = LocalDateTime.now(zone);
            return String.format("타임존: %s, 현재 시간: %s",
                    zone.getId(), now.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        } catch (Exception e) {
            return "알 수 없는 타임존: " + location;
        }
    }
}
