export async function api(path, {method = 'GET', data, token} = {}) {
  const headers = {};
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`/api${path}`, {method, headers, body: data === undefined ? undefined : JSON.stringify(data)});
  const payload = await response.json();
  if (!response.ok) {
    const detail = typeof payload.detail === 'string' ? payload.detail : '请检查表单字段和输入范围。';
    throw Object.assign(new Error(detail), {status: response.status});
  }
  return payload;
}
