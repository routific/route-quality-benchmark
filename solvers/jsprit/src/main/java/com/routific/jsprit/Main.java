package com.routific.jsprit;

import io.javalin.Javalin;

public class Main {

    public static void main(String[] args) {
        int port = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));

        Javalin app = Javalin.create(config -> {
            config.http.maxRequestSize = 100_000_000L; // 100MB
        }).start(port);

        app.get("/health", ctx -> ctx.result("ok"));

        app.post("/solve", ctx -> {
            SolveRequest req = ctx.bodyAsClass(SolveRequest.class);
            SolveResponse resp = JspritSolver.solve(req);
            ctx.json(resp);
        });
    }
}
