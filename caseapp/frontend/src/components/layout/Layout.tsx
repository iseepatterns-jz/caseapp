import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';

export const Layout: React.FC = () => {
    return (
        <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-primary)' }}>
            <Sidebar />
            <main style={{
                flex: 1,
                marginLeft: '280px',
                padding: '40px',
                maxWidth: '1600px',
                margin: '0 auto 0 280px'
            }}>
                <Outlet />
            </main>
        </div>
    );
};
