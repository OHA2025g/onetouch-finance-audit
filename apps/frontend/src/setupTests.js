import "@testing-library/jest-dom";
import { TextDecoder, TextEncoder } from "util";

// React Router 7 expects Web APIs in the Jest/jsdom environment.
if (typeof globalThis.TextEncoder === "undefined") globalThis.TextEncoder = TextEncoder;
if (typeof globalThis.TextDecoder === "undefined") globalThis.TextDecoder = TextDecoder;

