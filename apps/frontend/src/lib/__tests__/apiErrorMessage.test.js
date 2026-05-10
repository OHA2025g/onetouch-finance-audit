import { errorMessageFromAxios, errorMessageFromAxiosBlob } from "../apiErrorMessage";

describe("errorMessageFromAxios", () => {
  it("returns string detail", () => {
    expect(errorMessageFromAxios({ response: { data: { detail: "Not found" } } }, "x")).toBe("Not found");
  });

  it("joins validation error array", () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ["body", "name"], msg: "field required", type: "value_error.missing" },
            { loc: ["body", "amount"], msg: "ensure this value is greater than 0", type: "value_error.number" },
          ],
        },
      },
    };
    const msg = errorMessageFromAxios(err, "fallback");
    expect(msg).toContain("field required");
    expect(msg).toContain("greater than 0");
  });

  it("uses fallback when empty", () => {
    expect(errorMessageFromAxios({}, "none")).toBe("none");
  });
});

describe("errorMessageFromAxiosBlob", () => {
  it("reads JSON detail from axios blob-like body (duck-typed .text)", async () => {
    const data = {
      text: () => Promise.resolve(JSON.stringify({ detail: "Forbidden" })),
    };
    const msg = await errorMessageFromAxiosBlob({ response: { data } }, "fallback");
    expect(msg).toBe("Forbidden");
  });
});
