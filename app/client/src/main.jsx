import { StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import './theme.css';

import { RequireAuth } from './components/layout/RequireAuth';
import { AppLayout } from './components/layout/AppLayout';
import { AppProvider } from './store/AppContext';

import { Pages } from './pages';
import { Spinner } from './components/ui/Feedback';

const { Login, Signup, VerifyEmail, ForgotPassword, ResetPassword, Dashboard, Today, Companies, Pipeline, Outbox, Settings, Admin, Cv } =
  Pages;

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      {/* the sign-in pages; inside the app, AppLayout keeps its frame while a page loads */}
      <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route
          element={
            <RequireAuth>
              <AppProvider>
                <AppLayout />
              </AppProvider>
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="today" element={<Today />} />
          <Route path="companies" element={<Companies />} />
          <Route path="pipeline" element={<Pipeline />} />
          <Route path="outbox" element={<Outbox />} />
          <Route path="cv" element={<Cv />} />
          <Route path="settings" element={<Settings />} />
          <Route path="admin" element={<Admin />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  </StrictMode>
);
