package com.innovations.api.registry;

import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Configuration;

@Configuration
@ComponentScan(basePackages = {
        "com.innovations.api.registry",
        "com.innovations.api.exceptions"
})
public class RegistryConfig {}
