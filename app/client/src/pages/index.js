import { lazy } from 'react';

/*
 * Every page is its own file, so the first visit downloads only the page it lands on.
 * `preloadPages` fetches the rest once the browser is idle, so switching tabs later
 * never waits on the network.
 */
const loaders = {
  Login: () => import('./Login'),
  Signup: () => import('./Signup'),
  VerifyEmail: () => import('./VerifyEmail'),
  ForgotPassword: () => import('./ForgotPassword'),
  ResetPassword: () => import('./ResetPassword'),
  Dashboard: () => import('./Dashboard'),
  Today: () => import('./Today'),
  Companies: () => import('./Companies'),
  Pipeline: () => import('./Pipeline'),
  Outbox: () => import('./Outbox'),
  Settings: () => import('./Settings'),
  Admin: () => import('./Admin'),
  Cv: () => import('./Cv')
};

export const Pages = Object.fromEntries(Object.entries(loaders).map(([name, load]) => [name, lazy(load)]));

const APP_PAGES = ['Dashboard', 'Today', 'Companies', 'Pipeline', 'Outbox', 'Settings', 'Cv'];

export function preloadPages() {
  const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 1200));
  idle(() => APP_PAGES.forEach((name) => loaders[name]().catch(() => {})));
}
