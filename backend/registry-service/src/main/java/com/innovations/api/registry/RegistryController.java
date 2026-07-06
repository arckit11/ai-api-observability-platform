package com.innovations.api.registry;

import com.innovations.api.dto.ServiceDto;
import com.innovations.api.exceptions.ConflictException;
import com.innovations.api.exceptions.NotFoundException;
import jakarta.validation.Valid;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/registry/services")
public class RegistryController {

    private final ServiceRepository repo;

    public RegistryController(ServiceRepository repo) {
        this.repo = repo;
    }

    @GetMapping
    public List<ServiceDto> list() {
        return repo.findAll().stream().map(RegistryController::toDto).toList();
    }

    @GetMapping("/{id}")
    public ServiceDto get(@PathVariable UUID id) {
        return toDto(load(id));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ServiceDto create(@Valid @RequestBody ServiceDto.CreateRequest req) {
        if (repo.existsByNameAndEnvironment(req.name(), req.environment())) {
            throw new ConflictException(
                    "Service '%s' already registered in '%s'".formatted(req.name(), req.environment()));
        }
        ServiceEntity e = new ServiceEntity();
        e.setId(UUID.randomUUID());
        e.setName(req.name());
        e.setBaseUrl(req.baseUrl());
        e.setOwner(req.owner());
        e.setEnvironment(req.environment());
        e.setDescription(req.description());
        e.setCaptureTelemetry(req.captureTelemetry() == null ? true : req.captureTelemetry());
        OffsetDateTime now = OffsetDateTime.now();
        e.setCreatedAt(now);
        e.setUpdatedAt(now);
        return toDto(repo.save(e));
    }

    @PatchMapping("/{id}")
    public ServiceDto update(@PathVariable UUID id,
                             @Valid @RequestBody ServiceDto.UpdateRequest req) {
        ServiceEntity e = load(id);
        if (req.name() != null) e.setName(req.name());
        if (req.baseUrl() != null) e.setBaseUrl(req.baseUrl());
        if (req.owner() != null) e.setOwner(req.owner());
        if (req.environment() != null) e.setEnvironment(req.environment());
        if (req.description() != null) e.setDescription(req.description());
        if (req.captureTelemetry() != null) e.setCaptureTelemetry(req.captureTelemetry());
        e.setUpdatedAt(OffsetDateTime.now());
        return toDto(repo.save(e));
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable UUID id) {
        if (!repo.existsById(id)) throw new NotFoundException("Service " + id);
        repo.deleteById(id);
    }

    private ServiceEntity load(UUID id) {
        return repo.findById(id).orElseThrow(() -> new NotFoundException("Service " + id));
    }

    private static ServiceDto toDto(ServiceEntity e) {
        return new ServiceDto(
                e.getId(), e.getName(), e.getBaseUrl(), e.getOwner(), e.getEnvironment(),
                e.getDescription(), e.isCaptureTelemetry(), e.getCreatedAt(), e.getUpdatedAt()
        );
    }
}
