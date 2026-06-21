import React, { useState } from 'react';
import { Shield, User, Lock, ArrowRight, Activity } from 'lucide-react';

export default function Login({ onLogin }) {
  const [role, setRole] = useState('user'); // 'user' or 'admin'
  const [username, setUsername] = useState('Tej User');
  const [password, setPassword] = useState('••••••••');
  const [isLoading, setIsLoading] = useState(false);

  const handleRoleChange = (selectedRole) => {
    setRole(selectedRole);
    if (selectedRole === 'admin') {
      setUsername('Chirag Admin');
      setPassword('••••••••');
    } else {
      setUsername('Tej User');
      setPassword('••••••••');
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsLoading(true);
    // Simulate authentication delay for feedback
    setTimeout(() => {
      setIsLoading(false);
      onLogin(role);
    }, 1200);
  };

  return (
    <div className="login-page-container">
      {/* Dynamic Background Effects */}
      <div className="login-bg-glow blob-1"></div>
      <div className="login-bg-glow blob-2"></div>
      <div className="login-bg-grid"></div>

      <div className="login-card-wrapper">
        <div className="login-card-header">
          <div className="login-logo-circle flex-center">
            <Activity className="login-logo-icon" size={24} />
          </div>
          <h1 className="login-title">AGENTIC SUPERVISORY SUITE</h1>
          <p className="login-subtitle">Automatic Context Engineering & Compliance Audits</p>
        </div>

        {/* Role Selector Tabs */}
        <div className="role-selector-container">
          <button
            type="button"
            className={`role-select-btn flex-center ${role === 'user' ? 'active' : ''}`}
            onClick={() => handleRoleChange('user')}
          >
            <User size={18} className="role-icon" />
            <div className="role-btn-text">
              <span className="role-title-label">Tej User</span>
              <span className="role-subtitle-label">Supervisor Query</span>
            </div>
          </button>

          <button
            type="button"
            className={`role-select-btn flex-center ${role === 'admin' ? 'active' : ''}`}
            onClick={() => handleRoleChange('admin')}
          >
            <Shield size={18} className="role-icon" />
            <div className="role-btn-text">
              <span className="role-title-label">Chirag Admin</span>
              <span className="role-subtitle-label">ACE Configuration</span>
            </div>
          </button>
        </div>

        {/* Login Form */}
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-input-group">
            <label className="input-label-tag">Username</label>
            <div className="input-field-wrapper flex-center">
              <User size={16} className="input-field-icon" />
              <input
                type="text"
                className="login-text-input"
                placeholder="Enter username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
          </div>

          <div className="form-input-group">
            <label className="input-label-tag">Password</label>
            <div className="input-field-wrapper flex-center">
              <Lock size={16} className="input-field-icon" />
              <input
                type="password"
                className="login-text-input"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
          </div>

          <button type="submit" className="login-submit-btn flex-center" disabled={isLoading}>
            {isLoading ? (
              <div className="login-spinner"></div>
            ) : (
              <>
                <span>Access Platform</span>
                <ArrowRight size={16} className="submit-arrow-icon" />
              </>
            )}
          </button>
        </form>

        <div className="login-card-footer">
          <span>Secured by Advanced Role-Based Entitlements</span>
        </div>
      </div>
    </div>
  );
}
