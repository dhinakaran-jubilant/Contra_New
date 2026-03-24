import React from 'react';
import Layout from './Layout';
import ConsolidateView from './ConsolidateView';

const Consolidate = ({ user, onLogout }) => {
    return (
        <Layout user={user} onLogout={onLogout} activeMenu="consolidate">
            <ConsolidateView user={user} />
        </Layout>
    );
};

export default Consolidate;
