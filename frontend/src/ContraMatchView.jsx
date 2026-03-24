import React from 'react';
import Layout from './Layout';
import ContraMatch from './ContraMatch';

const Dashboard = ({ user, onLogout }) => {
    return (
        <Layout user={user} onLogout={onLogout} activeMenu="live">
            <ContraMatch user={user} />
        </Layout>
    );
};

export default Dashboard;
