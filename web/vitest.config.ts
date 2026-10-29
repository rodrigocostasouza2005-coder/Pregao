import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname),
      // "server-only" só faz sentido dentro do Next; nos testes é vazio
      "server-only": path.resolve(__dirname, "testes/vazio.ts"),
    },
  },
  test: { include: ["testes/**/*.test.ts"] },
});
