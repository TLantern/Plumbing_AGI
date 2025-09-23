#!/usr/bin/env node

/**
 * Google OAuth Test Script
 * Tests the Google Calendar OAuth integration
 */

const https = require('https');
const http = require('http');

// Configuration from .env
const config = {
  supabaseUrl: 'https://yzoalegdsogecfiqzfbp.supabase.co',
  supabaseAnonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl6b2FsZWdkc29nZWNmaXF6ZmJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc2NTMyNzIsImV4cCI6MjA3MzIyOTI3Mn0.rZe11f29kVYP9_oI3ER6NAHPrYs5r6U4ksasV272HGw',
  googleClientId: '20030545519-62boikt39ohgdrje8gbaga43ke1ukmsu.apps.googleusercontent.com',
  googleClientSecret: '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'
};

console.log('🔍 Google OAuth Integration Test');
console.log('================================\n');

// Test 1: Check Supabase connection
async function testSupabaseConnection() {
  console.log('1. Testing Supabase connection...');
  
  try {
    const response = await fetch(`${config.supabaseUrl}/rest/v1/`, {
      headers: {
        'apikey': config.supabaseAnonKey,
        'Authorization': `Bearer ${config.supabaseAnonKey}`
      }
    });
    
    if (response.ok) {
      console.log('✅ Supabase connection successful');
      return true;
    } else {
      console.log('❌ Supabase connection failed:', response.status, response.statusText);
      return false;
    }
  } catch (error) {
    console.log('❌ Supabase connection error:', error.message);
    return false;
  }
}

// Test 2: Check Google OAuth Edge Function
async function testGoogleOAuthFunction() {
  console.log('\n2. Testing Google OAuth Edge Function...');
  
  try {
    // First, we need to get a valid session token
    // For testing, we'll try to invoke the function directly
    const response = await fetch(`${config.supabaseUrl}/functions/v1/google-oauth`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.supabaseAnonKey}`,
        'apikey': config.supabaseAnonKey
      },
      body: JSON.stringify({
        action: 'get_auth_url'
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      console.log('✅ Google OAuth function accessible');
      console.log('   Auth URL generated:', data.authUrl ? 'Yes' : 'No');
      return true;
    } else {
      console.log('❌ Google OAuth function error:', data.error || response.statusText);
      return false;
    }
  } catch (error) {
    console.log('❌ Google OAuth function error:', error.message);
    return false;
  }
}

// Test 3: Validate Google OAuth Configuration
function testGoogleOAuthConfig() {
  console.log('\n3. Validating Google OAuth Configuration...');
  
  const issues = [];
  
  if (!config.googleClientId) {
    issues.push('Missing GOOGLE_CLIENT_ID');
  } else if (!config.googleClientId.includes('apps.googleusercontent.com')) {
    issues.push('Invalid GOOGLE_CLIENT_ID format');
  }
  
  if (!config.googleClientSecret) {
    issues.push('Missing GOOGLE_CLIENT_SECRET');
  } else if (!config.googleClientSecret.startsWith('GOCSPX-')) {
    issues.push('Invalid GOOGLE_CLIENT_SECRET format');
  }
  
  if (issues.length === 0) {
    console.log('✅ Google OAuth configuration valid');
    console.log('   Client ID:', config.googleClientId.substring(0, 20) + '...');
    console.log('   Client Secret:', config.googleClientSecret.substring(0, 10) + '...');
    return true;
  } else {
    console.log('❌ Google OAuth configuration issues:');
    issues.forEach(issue => console.log('   -', issue));
    return false;
  }
}

// Test 4: Check OAuth URL Generation
function testOAuthUrlGeneration() {
  console.log('\n4. Testing OAuth URL Generation...');
  
  try {
    const scopes = [
      'https://www.googleapis.com/auth/calendar.readonly',
      'https://www.googleapis.com/auth/userinfo.email',
      'https://www.googleapis.com/auth/userinfo.profile'
    ];
    
    const redirectUri = 'http://localhost:3000/dashboard';
    const state = 'test-user-id';
    
    const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
      `client_id=${config.googleClientId}&` +
      `redirect_uri=${encodeURIComponent(redirectUri)}&` +
      `scope=${encodeURIComponent(scopes.join(' '))}&` +
      `response_type=code&` +
      `access_type=offline&` +
      `prompt=consent&` +
      `state=${state}`;
    
    console.log('✅ OAuth URL generated successfully');
    console.log('   URL length:', authUrl.length);
    console.log('   Contains client_id:', authUrl.includes(config.googleClientId));
    console.log('   Contains redirect_uri:', authUrl.includes(redirectUri));
    console.log('   Contains scopes:', authUrl.includes('calendar.readonly'));
    
    return true;
  } catch (error) {
    console.log('❌ OAuth URL generation error:', error.message);
    return false;
  }
}

// Test 5: Check Frontend Integration
function testFrontendIntegration() {
  console.log('\n5. Checking Frontend Integration...');
  
  const issues = [];
  
  // Check if useGoogleOAuth hook exists
  try {
    const fs = require('fs');
    const hookPath = '/Users/tenbandz/Code/Plumbing_AGI/main_webpage/src/hooks/useGoogleOAuth.tsx';
    if (fs.existsSync(hookPath)) {
      console.log('✅ useGoogleOAuth hook exists');
    } else {
      issues.push('useGoogleOAuth hook not found');
    }
  } catch (error) {
    issues.push('Cannot check useGoogleOAuth hook');
  }
  
  // Check if Google Calendar component exists
  try {
    const fs = require('fs');
    const componentPath = '/Users/tenbandz/Code/Plumbing_AGI/main_webpage/src/components/calendar/GoogleCalendar.tsx';
    if (fs.existsSync(componentPath)) {
      console.log('✅ GoogleCalendar component exists');
    } else {
      issues.push('GoogleCalendar component not found');
    }
  } catch (error) {
    issues.push('Cannot check GoogleCalendar component');
  }
  
  if (issues.length === 0) {
    console.log('✅ Frontend integration files present');
    return true;
  } else {
    console.log('❌ Frontend integration issues:');
    issues.forEach(issue => console.log('   -', issue));
    return false;
  }
}

// Main test runner
async function runTests() {
  const results = [];
  
  results.push(await testSupabaseConnection());
  results.push(await testGoogleOAuthFunction());
  results.push(testGoogleOAuthConfig());
  results.push(testOAuthUrlGeneration());
  results.push(testFrontendIntegration());
  
  console.log('\n📊 Test Results Summary');
  console.log('========================');
  const passed = results.filter(r => r).length;
  const total = results.length;
  
  console.log(`Tests passed: ${passed}/${total}`);
  
  if (passed === total) {
    console.log('🎉 All tests passed! Google OAuth integration should be working.');
  } else {
    console.log('⚠️  Some tests failed. Check the issues above.');
  }
  
  console.log('\n🔧 Troubleshooting Tips:');
  console.log('1. Make sure Supabase Edge Functions are deployed');
  console.log('2. Verify Google OAuth credentials in Supabase dashboard');
  console.log('3. Check that redirect URIs are configured in Google Console');
  console.log('4. Ensure the frontend is running on the correct port');
  console.log('5. Check browser console for JavaScript errors');
}

// Run the tests
runTests().catch(console.error);
