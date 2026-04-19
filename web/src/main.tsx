import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createHashRouter, RouterProvider } from 'react-router';
import HomePage from './pages/HomePage';
import HistoryPage from './pages/HistoryPage';
import ProfilePage from './pages/ProfilePage';
import ShadowChatPage from './pages/ShadowChatPage';
import PersonalizePage from './pages/PersonalizePage';
import './styles/index.css';

const router = createHashRouter([
  { path: '/', element: <HomePage /> },
  { path: '/trace/:decisionId', element: <HomePage /> },
  { path: '/history', element: <HistoryPage /> },
  { path: '/reflect', element: <ShadowChatPage /> },
  { path: '/profile', element: <ProfilePage /> },
  { path: '/personalize', element: <PersonalizePage /> },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
);
