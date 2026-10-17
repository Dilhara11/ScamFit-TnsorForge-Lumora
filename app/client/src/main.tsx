import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, Link, RouterProvider } from 'react-router-dom';
import './index.css';
import { Layout } from './components/Layout';
import { Empty } from './components/ui';
import { ObservatoryProvider } from './lib/observatory';
import { Model } from './pages/Model';
import { Overview } from './pages/Overview';
import { Scan } from './pages/Scan';
import { VariantDetail } from './pages/VariantDetail';
import { Variants } from './pages/Variants';

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { index: true, element: <Overview /> },
      { path: 'scan', element: <Scan /> },
      { path: 'variants', element: <Variants /> },
      { path: 'variants/:id', element: <VariantDetail /> },
      { path: 'model', element: <Model /> },
      {
        path: '*',
        element: (
          <Empty icon={<span className="font-mono text-sm">404</span>} title="Page not found">
            <Link to="/" className="text-accent-700 hover:underline">Back to overview</Link>
          </Empty>
        ),
      },
    ],
  },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ObservatoryProvider>
      <RouterProvider router={router} />
    </ObservatoryProvider>
  </StrictMode>,
);
