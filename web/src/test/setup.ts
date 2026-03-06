import "@testing-library/jest-dom/vitest";

import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { clearApiConfigStorage } from "../config";

afterEach(() => {
  cleanup();
  clearApiConfigStorage();
});
