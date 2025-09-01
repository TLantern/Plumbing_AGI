import { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

// Global variable to track last log positions
let logPositions: { [key: string]: number } = {};

// Function to read recent log entries
function getRecentLogs(logFile: string, maxLines: number = 50): string[] {
  try {
    if (!fs.existsSync(logFile)) {
      return [];
    }
    
    const content = fs.readFileSync(logFile, 'utf8');
    const lines = content.split('\n').filter(line => line.trim());
    return lines.slice(-maxLines);
  } catch (error) {
    console.error(`Error reading log file ${logFile}:`, error);
    return [];
  }
}

// Function to get new log entries since last check
function getNewLogs(logFile: string): string[] {
  try {
    if (!fs.existsSync(logFile)) {
      return [];
    }
    
    const stats = fs.statSync(logFile);
    const currentSize = stats.size;
    const lastPosition = logPositions[logFile] || 0;
    
    if (currentSize < lastPosition) {
      // File was rotated, start from beginning
      logPositions[logFile] = 0;
      return getRecentLogs(logFile, 20);
    }
    
    if (currentSize === lastPosition) {
      return []; // No new content
    }
    
    // Read the new content synchronously
    const newContent = fs.readFileSync(logFile, 'utf8').slice(lastPosition);
    logPositions[logFile] = currentSize;
    
    return newContent.split('\n').filter(line => line.trim());
  } catch (error) {
    console.error(`Error reading new logs from ${logFile}:`, error);
    return [];
  }
}

// Function to parse call events from logs
function parseCallEvents(logLines: string[]): any[] {
  const callEvents: any[] = [];
  
  for (const line of logLines) {
    if (line.includes('CALL_EVENT') || line.includes('📞')) {
      try {
        // Extract call information from log line
        const timestampMatch = line.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/);
        const callSidMatch = line.match(/Call ([A-Za-z0-9_]+)/);
        const eventMatch = line.match(/\[([A-Z_]+)\]/);
        
        if (timestampMatch && callSidMatch) {
          callEvents.push({
            timestamp: timestampMatch[1],
            call_sid: callSidMatch[1],
            event_type: eventMatch ? eventMatch[1] : 'UNKNOWN',
            message: line.trim()
          });
        }
      } catch (error) {
        // Skip malformed lines
        continue;
      }
    }
  }
  
  return callEvents;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  try {
    // Get salon analytics service URL from environment or default
    const salonServiceUrl = process.env.SALON_SERVICE_URL || 'http://localhost:5002';
    
    // Fetch dashboard data from salon analytics service
    const response = await fetch(`${salonServiceUrl}/salon/dashboard`);
    
    let dashboardData;
    if (!response.ok) {
      // Throw error for any bad status codes
      throw new Error(`Salon service returned ${response.status}: ${response.statusText}`);
    } else {
      dashboardData = await response.json();
    }
    
    // Get real-time log data
    const logFiles = [
      'logs/salon_calls_realtime.log',
      'logs/salon_phone.log'
    ];
    
    const recentLogs: string[] = [];
    const callEvents: any[] = [];
    
    try {
      for (const logFile of logFiles) {
        const logPath = path.join(process.cwd(), '..', logFile);
        const newLogs = getNewLogs(logPath);
        recentLogs.push(...newLogs);
        callEvents.push(...parseCallEvents(newLogs));
      }
    } catch (logError) {
      console.warn('Failed to read log files:', logError);
      // Continue without log data rather than failing the entire request
    }
    
    // Add real-time data to dashboard
    const enhancedData = {
      ...dashboardData,
      real_time: {
        last_updated: new Date().toISOString(),
        recent_call_events: callEvents.slice(-10), // Last 10 call events
        log_activity: recentLogs.length > 0,
        active_logs: recentLogs.slice(-5) // Last 5 log entries
      }
    };
    
    return res.status(200).json(enhancedData);
    
  } catch (error) {
    console.error('Failed to fetch salon dashboard data:', error);
    
    // Throw error instead of returning mock data
    return res.status(500).json({ 
      error: 'Failed to fetch salon dashboard data',
      details: error instanceof Error ? error.message : 'Unknown error'
    });
  }
}

function getMockSalonData() {
  const now = new Date();
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay()); // Start of current week
  
  return {
    current_week: {
      week_start: weekStart.toISOString(),
      call_metrics: {
        total_calls: 15,
        answered_calls: 12,
        missed_calls: 3,
        after_hours_calls: 2,
        average_call_duration: 185, // seconds
        conversion_rate: 75.0
      },
      appointment_metrics: {
        total_appointments: 9,
        completed_appointments: 7,
        no_shows: 1,
        cancellations: 1,
        no_show_rate: 11.1,
        cancellation_rate: 11.1,
        average_revenue_per_appointment: 85.0,
        total_revenue: 595.0
      },
      growth_rate: 12.5,
      new_customers: 3,
      returning_customers: 6
    },
    active_calls: 0,
    recent_calls: [
      {
        call_sid: 'call_001',
        phone_number: '+1234567890',
        direction: 'inbound',
        start_time: new Date(Date.now() - 3600000).toISOString(),
        answered: true,
        after_hours: false
      },
      {
        call_sid: 'call_002',
        phone_number: '+1234567891',
        direction: 'inbound',
        start_time: new Date(Date.now() - 7200000).toISOString(),
        answered: false,
        after_hours: true
      }
    ],
    growth_insights: {
      revenue_growth_4_week: 15.8,
      appointment_growth_4_week: 22.5,
      avg_no_show_rate: 8.5,
      avg_conversion_rate: 72.3,
      insights: [
        'Excellent revenue growth of 15.8% over the last 4 weeks',
        'High call-to-appointment conversion rate indicates effective booking process',
        'Low no-show rate shows good customer commitment'
      ],
      recommendations: [
        'Consider extending hours to capture after-hours demand',
        'Implement loyalty program to maintain growth momentum',
        'Add online booking to reduce phone volume during peak hours'
      ],
      current_week: {
        total_calls: 15,
        appointments: 9,
        revenue: 595.0,
        avg_revenue_per_appointment: 85.0
      }
    },
    timestamp: new Date().toISOString()
  };
}
