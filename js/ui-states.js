export function showLoading(status) {
  status.hidden = false;
  status.className = "status";
  status.textContent = "กำลังโหลดเนื้อหา";
}

export function showEmpty(status) {
  status.hidden = false;
  status.className = "status empty";
  status.textContent = "ยังไม่มีบทความ";
}

export function showError(status, message, onRetry) {
  status.hidden = false;
  status.className = "status error";
  status.textContent = "";
  const text = document.createElement("p");
  text.textContent = message || "โหลดเนื้อหาไม่สำเร็จ";
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "ลองใหม่";
  button.addEventListener("click", onRetry);
  status.append(text, button);
}

export function hideStatus(status) {
  status.hidden = true;
  status.textContent = "";
}
