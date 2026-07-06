package com.innovations.api.registry;

import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ServiceRepository extends JpaRepository<ServiceEntity, UUID> {
    boolean existsByNameAndEnvironment(String name, String environment);
}
