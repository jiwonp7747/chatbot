package ai.bistelligence.chat_backend_spring.domain.user.enums;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum UserStatus {
    ACTIVE("활성"),
    INACTIVE("비활성"),
    DELETED("삭제"),
    ;

    private final String description;
}
