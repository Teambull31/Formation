import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';

// Évite la page blanche : une erreur de rendu affiche un message et permet de recharger.
class ErrorBoundary extends React.Component<{children: React.ReactNode}, {error: Error | null}> {
  state = {error: null as Error | null};

  static getDerivedStateFromError(error: Error) {
    return {error};
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" style={{padding: 24, maxWidth: 560, margin: '48px auto', fontFamily: 'sans-serif', color: '#e2e8f0'}}>
        <h1 style={{fontSize: 20, fontWeight: 800, marginBottom: 8}}>Une erreur est survenue</h1>
        <p style={{opacity: 0.8, marginBottom: 16}}>{this.state.error.message}</p>
        <button onClick={() => window.location.reload()} style={{padding: '8px 16px', borderRadius: 8, background: '#f59e0b', color: '#0f172a', fontWeight: 700}}>
          Recharger
        </button>
      </div>
    );
  }
}

createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
