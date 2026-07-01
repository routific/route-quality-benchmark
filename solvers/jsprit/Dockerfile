FROM gradle:8.5-jdk17 AS builder
WORKDIR /app
# Copy build files first so dependency downloads are cached separately from source changes
COPY settings.gradle build.gradle ./
COPY src ./src
RUN gradle shadowJar --no-daemon

FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
COPY --from=builder /app/build/libs/jsprit-service-1.0.0.jar app.jar
EXPOSE 8080
CMD ["java", "-Xmx4g", "-jar", "app.jar"]
