package com.innovations.api.collector;

import org.springframework.data.jpa.repository.JpaRepository;

public interface ApiLogRepository extends JpaRepository<ApiLogEntity, Long> {
    boolean existsByDedupKey(String dedupKey);
}
