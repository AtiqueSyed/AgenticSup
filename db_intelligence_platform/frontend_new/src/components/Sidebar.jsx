/* eslint-disable */
import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageSquare, 
  Edit3, 
  History, 
  Newspaper, 
  Wrench, 
  Users, 
  MessageSquareWarning, 
  BookOpen, 
  Sun, 
  Moon, 
  Globe, 
  Menu, 
  Search, 
  Trash2,
  LogOut
} from 'lucide-react';

const TRANSLATIONS = {
  en: {
    chat: 'Chat',
    edit: 'Edit',
    history: 'History',
    news: 'News',
    instruct: 'Instruct',
    team: 'Team',
    feedback: 'Feedback',
    guide: 'Guide',
    lightMode: 'Light Mode',
    darkMode: 'Dark Mode',
    hindi: 'हिंदी',
    english: 'English',
    recentChats: 'Recent chats',
    searchChats: 'Search messages...',
    today: 'Today',
    may7: 'May 7',
    may6: 'May 6',
    apr29: 'April 29',
    sbiQuery: 'Based on your Performance Appraisal Report ...',
    complianceQuery: 'Based on the available records, the Reserve ...',
    evaluationQuery: 'Based on the search results from the Bank da...',
    masterCircular: 'Based on the Master Circular on Promotion P...',
  },
  hi: {
    chat: 'चैट (Chat)',
    edit: 'संपादन (Edit)',
    history: 'इतिहास (History)',
    news: 'समाचार (News)',
    instruct: 'निर्देश (Instruct)',
    team: 'टीम (Team)',
    feedback: 'प्रतिक्रिया',
    guide: 'गाइड (Guide)',
    lightMode: 'लाइट मोड',
    darkMode: 'डार्क मोड',
    hindi: 'हिंदी',
    english: 'English',
    recentChats: 'हालिया चैट',
    searchChats: 'खोजें...',
    today: 'आज',
    may7: '७ मई',
    may6: '६ मई',
    apr29: '२९ अप्रैल',
    sbiQuery: 'आपके प्रदर्शन मूल्यांकन रिपोर्ट के आधार पर ...',
    complianceQuery: 'उपलब्ध अभिलेखों के आधार पर, रिजर्व ...',
    evaluationQuery: 'बैंक डेटा के खोज परिणामों के आधार पर...',
    masterCircular: 'पदोन्नति नीति पर मास्टर परिपत्र के आधार पर...',
  }
};

export default function Sidebar({ 
  activeTab, 
  setActiveTab, 
  lang, 
  setLang, 
  theme, 
  toggleTheme, 
  isCollapsed, 
  setIsCollapsed,
  onLoadPastChat,
  recentChats,
  onDeleteChatSession,
  onClearAllChats,
  onLogout
}) {
  const [showRecentPopup, setShowRecentPopup] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const popoverRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (
        showRecentPopup &&
        popoverRef.current &&
        !popoverRef.current.contains(event.target) &&
        !event.target.closest('.sidebar-nav')
      ) {
        setShowRecentPopup(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showRecentPopup]);
  
  const t = TRANSLATIONS[lang];

  const handleNavClick = (tabId) => {
    setActiveTab(tabId);
    if (tabId === 'history' || tabId === 'edit') {
      setShowRecentPopup(!showRecentPopup);
    } else {
      setShowRecentPopup(false);
    }
  };

  const filteredChats = recentChats.filter(chat => {
    const labelText = chat.labelKey ? t[chat.labelKey] : chat.summary;
    const text = (labelText || '').toLowerCase() + chat.queryText.toLowerCase();
    return text.includes(searchQuery.toLowerCase());
  });

  return (
    <div className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Sidebar Header */}
      <div className="sidebar-header">
        <div className="logo-section">
          {/* Pulsing ChiRAG logo circle */}
          <div className="logo-ring">
            <div className="logo-dots"></div>
          </div>
          {!isCollapsed && (
            <div className="logo-text-container">
              <span className="gen-beta-badge">Gen Beta</span>
              <span className="logo-text">ChiRAG</span>
            </div>
          )}
        </div>
        <button 
          className="toggle-sidebar-btn flex-center"
          onClick={() => setIsCollapsed(!isCollapsed)}
          aria-label="Toggle Sidebar"
        >
          <Menu size={20} />
        </button>
      </div>

      {/* Navigation List */}
      <nav className="sidebar-nav">
        <ul>
          <li className={activeTab === 'chat' ? 'active' : ''}>
            <button onClick={() => handleNavClick('chat')}>
              <MessageSquare size={18} className="nav-icon" />
              {!isCollapsed && <span>{t.chat}</span>}
            </button>
          </li>
          
          <li className={activeTab === 'edit' ? 'active' : ''}>
            <button onClick={() => handleNavClick('edit')}>
              <Edit3 size={18} className="nav-icon" />
              {!isCollapsed && <span>{t.edit}</span>}
            </button>
          </li>

          <li className={activeTab === 'history' ? 'active' : ''}>
            <button onClick={() => handleNavClick('history')}>
              <History size={18} className="nav-icon" />
              {!isCollapsed && <span>{t.history}</span>}
            </button>
          </li>

          <li className={activeTab === 'news' ? 'active' : ''}>
            <button onClick={() => handleNavClick('news')}>
              <Newspaper size={18} className="nav-icon" />
              {!isCollapsed && <span>{t.news}</span>}
            </button>
          </li>

          <li className={activeTab === 'instruct' ? 'active' : ''}>
            <button onClick={() => handleNavClick('instruct')}>
              <Wrench size={18} className="nav-icon" />
              {!isCollapsed && <span>{t.instruct}</span>}
            </button>
          </li>

          <li className={activeTab === 'team' ? 'active' : ''}>
            <button onClick={() => handleNavClick('team')}>
              <Users size={18} className="nav-icon" />
              {!isCollapsed && <span>{t.team}</span>}
            </button>
          </li>

          <li className={activeTab === 'feedback' ? 'active' : ''}>
            <button onClick={() => handleNavClick('feedback')}>
              <MessageSquareWarning size={18} className="nav-icon" />
              {!isCollapsed && <span>{t.feedback}</span>}
            </button>
          </li>

          <li className={activeTab === 'guide' ? 'active' : ''}>
            <button onClick={() => handleNavClick('guide')}>
              <BookOpen size={18} className="nav-icon" />
              {!isCollapsed && <span>{t.guide}</span>}
            </button>
          </li>

          <hr className="nav-divider" />

          {/* Theme Toggle */}
          <li>
            <button onClick={toggleTheme}>
              {theme === 'dark' ? (
                <>
                  <Sun size={18} className="nav-icon" />
                  {!isCollapsed && <span>{t.lightMode}</span>}
                </>
              ) : (
                <>
                  <Moon size={18} className="nav-icon" />
                  {!isCollapsed && <span>{t.darkMode}</span>}
                </>
              )}
            </button>
          </li>

          {/* Language Toggle */}
          <li>
            <button onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}>
              <Globe size={18} className="nav-icon" />
              {!isCollapsed && <span>{lang === 'en' ? 'हिंदी' : 'English'}</span>}
            </button>
          </li>

          {/* Logout Button */}
          {onLogout && (
            <li>
              <button onClick={onLogout} style={{ color: '#ef4444' }}>
                <LogOut size={18} className="nav-icon" />
                {!isCollapsed && <span>Logout</span>}
              </button>
            </li>
          )}
        </ul>
      </nav>

      {/* RBI Logo Footer */}
      <div className="sidebar-footer">
        <div className="rbi-seal-container flex-center">
          <svg className="rbi-seal-svg" viewBox="0 0 100 100" width="42" height="42">
            <circle cx="50" cy="50" r="46" fill="transparent" stroke="var(--rbi-gold)" strokeWidth="2.5" />
            <circle cx="50" cy="50" r="42" fill="transparent" stroke="var(--rbi-gold)" strokeWidth="1" />
            <path d="M 50,15 C 32,15 25,32 25,50 C 25,68 32,85 50,85 C 68,85 75,68 75,50 C 75,32 68,15 50,15 Z" fill="transparent" stroke="var(--rbi-gold)" strokeWidth="1.5" strokeDasharray="3,3" />
            <text id="rbi-seal-text" fill="var(--rbi-gold)" fontSize="7" fontWeight="bold" textAnchor="middle">
              <textPath href="#rbi-seal-text-path" startOffset="50%">RESERVE BANK OF INDIA</textPath>
            </text>
            <path id="rbi-seal-text-path" d="M 20,50 A 30,30 0 1,1 80,50" fill="none" />
            {/* Minimal stylized lion emblem silhouette inside seal */}
            <path d="M 44,40 C 44,38 48,34 50,34 C 52,34 56,38 56,40 C 56,45 54,48 54,54 C 54,60 52,65 52,68 C 50,68 49,66 48,65 L 46,65 C 46,60 44,52 44,40 Z" fill="var(--rbi-gold)" />
            <path d="M 40,55 C 38,55 37,58 37,60 C 37,62 39,63 41,63 C 43,63 43,60 43,58 Z" fill="var(--rbi-gold)" />
            <path d="M 60,55 C 62,55 63,58 63,60 C 63,62 61,63 59,63 C 57,63 57,60 57,58 Z" fill="var(--rbi-gold)" />
          </svg>
        </div>
        {!isCollapsed && (
          <div className="rbi-text-container">
            <span className="rbi-caption-hi">भारतीय रिज़र्व बैंक</span>
            <span className="rbi-caption-en">RESERVE BANK OF INDIA</span>
          </div>
        )}
      </div>

      {/* Recent Chats Popover Menu (Matches image 1) */}
      {showRecentPopup && (
        <div ref={popoverRef} className="recent-chats-popover" style={{ left: isCollapsed ? '76px' : '236px' }}>
          <div className="popover-header">
            <span>{t.recentChats}</span>
            <button className="delete-all-chats flex-center" onClick={onClearAllChats} aria-label="Clear all histories">
              <Trash2 size={15} />
            </button>
          </div>
          
          <div className="popover-search">
            <Search size={14} className="search-icon" />
            <input 
              type="text" 
              placeholder={t.searchChats} 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="popover-chat-list">
            {/* Filter group: Today */}
            {filteredChats.some(c => c.dateKey === 'today') && (
              <div className="chat-date-group">
                <span className="date-group-header">{t.today}</span>
                {filteredChats.filter(c => c.dateKey === 'today').map(chat => (
                  <div key={chat.id} className="popover-chat-item-row">
                    <button 
                      className="popover-chat-item-btn"
                      onClick={() => {
                        onLoadPastChat(chat.queryText);
                        setShowRecentPopup(false);
                      }}
                    >
                      {chat.labelKey ? t[chat.labelKey] : chat.summary}
                    </button>
                    <button 
                      className="delete-chat-session-btn flex-center"
                      onClick={() => onDeleteChatSession(chat.id)}
                      title="Delete chat session"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Filter group: May 7 */}
            {filteredChats.some(c => c.dateKey === 'may7') && (
              <div className="chat-date-group">
                <span className="date-group-header">{t.may7}</span>
                {filteredChats.filter(c => c.dateKey === 'may7').map(chat => (
                  <div key={chat.id} className="popover-chat-item-row">
                    <button 
                      className="popover-chat-item-btn"
                      onClick={() => {
                        onLoadPastChat(chat.queryText);
                        setShowRecentPopup(false);
                      }}
                    >
                      {chat.labelKey ? t[chat.labelKey] : chat.summary}
                    </button>
                    <button 
                      className="delete-chat-session-btn flex-center"
                      onClick={() => onDeleteChatSession(chat.id)}
                      title="Delete chat session"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Filter group: May 6 */}
            {filteredChats.some(c => c.dateKey === 'may6') && (
              <div className="chat-date-group">
                <span className="date-group-header">{t.may6}</span>
                {filteredChats.filter(c => c.dateKey === 'may6').map(chat => (
                  <div key={chat.id} className="popover-chat-item-row">
                    <button 
                      className="popover-chat-item-btn"
                      onClick={() => {
                        onLoadPastChat(chat.queryText);
                        setShowRecentPopup(false);
                      }}
                    >
                      {chat.labelKey ? t[chat.labelKey] : chat.summary}
                    </button>
                    <button 
                      className="delete-chat-session-btn flex-center"
                      onClick={() => onDeleteChatSession(chat.id)}
                      title="Delete chat session"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {filteredChats.length === 0 && (
              <div className="popover-empty-state">No matching chats found</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
