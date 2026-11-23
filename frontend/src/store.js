export const store = {
  token: sessionStorage.getItem('museum-token'), staff: null,
  loans: [], record: null, schedule: [], scheduleDay: '',
};

export function saveSession(session) {
  store.token = session?.token ?? null;
  store.staff = session?.staff ?? null;
  if (store.token) sessionStorage.setItem('museum-token', store.token);
  else sessionStorage.removeItem('museum-token');
}
