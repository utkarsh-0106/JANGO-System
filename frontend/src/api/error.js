export function getApiErrorMessage(error, fallback = "Something went wrong.") {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || "Invalid input")
      .join(", ");
  }

  if (detail && typeof detail === "object") {
    return detail.msg || "Invalid request.";
  }

  return fallback;
}
