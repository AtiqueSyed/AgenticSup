/* eslint-disable */
import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import KnowledgeSidebar from './components/KnowledgeSidebar';
import Login from './components/Login';
import ACEOnboarding from './components/ACEOnboarding';
import MetadataRegistry from './components/MetadataRegistry';
import { navigate, usePath } from './router';
import { resolveRoute, adminTabForPath, pathForAdminTab } from './routes';
import './App.css';

// Session storage throws in a few locked-down browser configurations; a failure here
// only costs the user a re-login on refresh, so it must never take the app down.
const readRole = () => {
  try { return sessionStorage.getItem('userRole'); } catch { return null; }
};
const writeRole = (role) => {
  try {
    role ? sessionStorage.setItem('userRole', role) : sessionStorage.removeItem('userRole');
  } catch { /* refresh will simply land back on /login */ }
};

export default function App() {
  const path = usePath();
  // Persisted so that a deep link or a refresh on /admin/registry does not bounce to
  // login every time. This is a UI role switch, not authentication -- there is no
  // credential check behind it yet, so nothing is being weakened by storing it.
  const [userRole, setUserRole] = useState(readRole);
  const [activeTab, setActiveTab] = useState('chat');
  const [lang, setLang] = useState('en');
  const [theme, setTheme] = useState('light');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isRightSidebarCollapsed, setIsRightSidebarCollapsed] = useState(false);
  
  // Lifted Recent Chats state to synchronize Sidebar and Chat updates
  const [recentChats, setRecentChats] = useState([
    { id: 'appraisal', dateKey: 'today', labelKey: 'sbiQuery', queryText: 'What is my supervisory evaluation?' },
    { id: 'sbi-penalty', dateKey: 'today', labelKey: 'complianceQuery', queryText: 'What are the issues for which SBI has been penalised by RBI in the recent past?' },
    { id: 'compare-penalties', dateKey: 'may7', labelKey: 'evaluationQuery', queryText: 'Compare penalties by bank' },
    { id: 'compliance-logs', dateKey: 'may6', labelKey: 'masterCircular', queryText: 'Show compliance ratings' }
  ]);

  // Initialize uploaded files with Master Direction on RTI PDF as shown in the requested settings
  const [uploadedFiles, setUploadedFiles] = useState([
    { id: 'rti-direction', name: 'Master Direction on RTI.pdf', size: '245.2 KB', type: 'pdf' }
  ]);
  
  // Context query loaded from sidebar history popover
  const [presetQuery, setPresetQuery] = useState('');

  const route = resolveRoute(userRole, path);

  // Redirects are replacements, never pushes: a bounced-off URL must not become a
  // history entry, or Back would walk the user straight back into the bounce.
  useEffect(() => {
    if (route.redirect) navigate(route.redirect, { replace: true });
  }, [route.redirect]);

  // Sync theme to root body element for global dark/light styling changes
  useEffect(() => {
    document.body.className = theme === 'light' ? 'light-theme' : 'dark-theme';
  }, [theme]);

  // Handle loading historical chats from the Sidebar popover
  const handleLoadPastChat = (queryText) => {
    setActiveTab('chat');
    setPresetQuery(queryText);
  };

  // Add new query submitted in chat to the Recent Chats lists
  const handleNewChatSession = (queryText) => {
    // Avoid double entries for identical queries
    if (recentChats.some(c => c.queryText.toLowerCase() === queryText.toLowerCase())) return;
    
    const newChatObj = {
      id: Math.random().toString(36).substr(2, 9),
      dateKey: 'today',
      labelKey: null,
      queryText: queryText,
      summary: queryText.length > 36 ? queryText.substring(0, 36) + '...' : queryText
    };
    setRecentChats(prev => [newChatObj, ...prev]);
  };

  // Delete specific chat session from the list
  const handleDeleteChatSession = (id) => {
    setRecentChats(prev => prev.filter(c => c.id !== id));
  };

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  // Login and logout only move the role; the effect above works out the destination.
  const handleLogin = (role) => { writeRole(role); setUserRole(role); };
  const handleLogout = () => { writeRole(null); setUserRole(null); };

  // Derived from the URL rather than held in state, so browser back/forward moves
  // between admin screens and both admin components keep their original prop API.
  const adminActiveTab = adminTabForPath(path);
  const setAdminActiveTab = (tab) => navigate(pathForAdminTab(tab));

  // The redirect effect is mid-flight; rendering the old view here would flash it.
  if (route.redirect) return null;

  if (route.view === 'login') {
    return <Login onLogin={handleLogin} />;
  }

  if (route.view === 'onboarding') {
    return (
      <ACEOnboarding 
        onLogout={handleLogout} 
        adminActiveTab={adminActiveTab}
        setAdminActiveTab={setAdminActiveTab}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    );
  }

  if (route.view === 'registry') {
    return (
      <MetadataRegistry 
        onLogout={handleLogout} 
        adminActiveTab={adminActiveTab}
        setAdminActiveTab={setAdminActiveTab}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    );
  }

  return (
    <div className={`app-container ${theme}-theme${userRole === 'admin' ? ' has-admin-banner' : ''}`}>
      {/* Admin header helper if logged in as admin in query view */}
      {userRole === 'admin' && (
        <div className="admin-query-header flex-center">
          <div className="admin-badge flex-center">
            <span className="admin-session-dot"></span>
            <span>Admin Test Session</span>
          </div>
          <button 
            type="button" 
            className="admin-dashboard-btn" 
            onClick={() => setAdminActiveTab('onboarding')}
          >
            Go to Admin Dashboard
          </button>
        </div>
      )}

      {/* 1. Left Sidebar Navigation */}
      <Sidebar 
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        lang={lang}
        setLang={setLang}
        theme={theme}
        toggleTheme={toggleTheme}
        isCollapsed={isSidebarCollapsed}
        setIsCollapsed={setIsSidebarCollapsed}
        onLoadPastChat={handleLoadPastChat}
        recentChats={recentChats}
        onDeleteChatSession={handleDeleteChatSession}
        onClearAllChats={() => setRecentChats([])}
        onLogout={handleLogout}
      />

      {/* 2. Main Workspace (Locked exclusively to General Chat Interface) */}
      <main className="main-workspace">
        <ChatInterface 
          lang={lang} 
          theme={theme}
          presetQuery={presetQuery}
          clearPresetQuery={() => setPresetQuery('')}
          onNewChatSession={handleNewChatSession}
          userRole={userRole}
        />
      </main>

      {/* 3. Right Sidebar (Build Knowledge) */}
      <KnowledgeSidebar 
        lang={lang}
        uploadedFiles={uploadedFiles}
        setUploadedFiles={setUploadedFiles}
        isRightSidebarCollapsed={isRightSidebarCollapsed}
        setIsRightSidebarCollapsed={setIsRightSidebarCollapsed}
      />
    </div>
  );
}
