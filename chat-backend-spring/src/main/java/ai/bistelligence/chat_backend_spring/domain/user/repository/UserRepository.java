package ai.bistelligence.chat_backend_spring.domain.user.repository;

import ai.bistelligence.chat_backend_spring.domain.user.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserRepository extends JpaRepository<User, String> {
}
