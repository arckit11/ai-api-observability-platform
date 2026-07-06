# Generic Spring Boot service image. Build args:
#   SERVICE_MODULE  Maven module directory under backend/ (e.g. gateway-service)
#   JAR_NAME        Final jar name (defaults to $SERVICE_MODULE-*.jar)
#
# Build from repo root:
#   docker build -f deploy/docker/backend-service.Dockerfile \
#                --build-arg SERVICE_MODULE=gateway-service \
#                -t iapi/gateway-service:dev .

# ─── Build stage ─────────────────────────────────────────────
FROM maven:3.9-eclipse-temurin-21 AS builder
ARG SERVICE_MODULE
WORKDIR /workspace
COPY backend/pom.xml backend/pom.xml
COPY backend/shared backend/shared
COPY backend/${SERVICE_MODULE} backend/${SERVICE_MODULE}
RUN mvn -B -f backend/pom.xml -pl shared/common-dto,shared/common-events,shared/common-security,shared/common-utils,shared/common-exceptions,${SERVICE_MODULE} -am package -DskipTests

# ─── Runtime stage ───────────────────────────────────────────
FROM eclipse-temurin:21-jre-alpine
ARG SERVICE_MODULE
WORKDIR /app
COPY --from=builder /workspace/backend/${SERVICE_MODULE}/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
