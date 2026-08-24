/* eslint-disable */
import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import KnowledgeSidebar from './components/KnowledgeSidebar';
import Login from './components/Login';
import ACEOnboarding from './components/ACEOnboarding';
import MetadataRegistry from './components/MetadataRegistry';
import './App.css';

export default function App() {
  const [userRole, setUserRole] = useState(null); // 'user' | 'admin' | null
  const [adminActiveTab, setAdminActiveTab] = useState('onboarding'); // 'onboarding' | 'query'
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

  // Sync theme to root body element for global dark/light styling changes
  useEffect(() => {
    document.body.className = theme === 'light' ? 'light-theme' : 'dark-theme';
  }, [theme]);


  if (userRole === null) {
    return <Login onLogin={(role) => setUserRole(role)} />;
  }

  if (userRole === 'admin' && adminActiveTab === 'onboarding') {
    return (
      <ACEOnboarding 
        onLogout={() => setUserRole(null)} 
        adminActiveTab={adminActiveTab}
        setAdminActiveTab={setAdminActiveTab}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    );
  }

  if (userRole === 'admin' && adminActiveTab === 'registry') {
    return (
      <MetadataRegistry 
        onLogout={() => setUserRole(null)} 
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
        onLogout={() => {
          setUserRole(null);
          setAdminActiveTab('onboarding');
        }}
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
