import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 20,
  duration: '30s',
};

const BASE_URL = 'http://localhost';

export function setup() {
  const users = [];
  for (let i = 0; i < options.vus; i++) {
    const email = `k6-loadtest-${i}@example.com`;
    const password = 'LoadTestPassword123';
    http.post(
      `${BASE_URL}/auth/register`,
      JSON.stringify({ email, password }),
      { headers: { 'Content-Type': 'application/json' } }
    );
    users.push({ email, password });
  }
  return { users };
}

export default function (data) {
  const user = data.users[(__VU - 1) % data.users.length];
  const res = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email: user.email, password: user.password }),
    { headers: { 'Content-Type': 'application/json' } }
  );

  check(res, {
    'login succeeded': (r) => r.status === 200,
  });

  // Deliberately spaced so each account stays under the 10-per-60s login rate
  // limit — this measures baseline endpoint performance, not the limiter itself
  // (already confirmed working by hand on Day 3/4).
  sleep(5);
}