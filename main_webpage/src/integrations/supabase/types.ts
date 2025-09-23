export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "13.0.5"
  }
  public: {
    Tables: {
      appointments: {
        Row: {
          appointment_date: string | null
          call_id: string | null
          created_at: string | null
          estimated_revenue_cents: number | null
          id: string
          salon_id: string | null
          service_id: string | null
          status: string | null
          updated_at: string | null
        }
        Insert: {
          appointment_date?: string | null
          call_id?: string | null
          created_at?: string | null
          estimated_revenue_cents?: number | null
          id?: string
          salon_id?: string | null
          service_id?: string | null
          status?: string | null
          updated_at?: string | null
        }
        Update: {
          appointment_date?: string | null
          call_id?: string | null
          created_at?: string | null
          estimated_revenue_cents?: number | null
          id?: string
          salon_id?: string | null
          service_id?: string | null
          status?: string | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "appointments_call_id_fkey"
            columns: ["call_id"]
            isOneToOne: false
            referencedRelation: "calls"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "appointments_salon_id_fkey"
            columns: ["salon_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "appointments_service_id_fkey"
            columns: ["service_id"]
            isOneToOne: false
            referencedRelation: "services"
            referencedColumns: ["id"]
          },
        ]
      }
      audit_logs: {
        Row: {
          action: string
          created_at: string
          id: string
          ip_address: unknown | null
          record_id: string | null
          sensitive_fields: string[] | null
          table_name: string
          user_agent: string | null
          user_id: string | null
        }
        Insert: {
          action: string
          created_at?: string
          id?: string
          ip_address?: unknown | null
          record_id?: string | null
          sensitive_fields?: string[] | null
          table_name: string
          user_agent?: string | null
          user_id?: string | null
        }
        Update: {
          action?: string
          created_at?: string
          id?: string
          ip_address?: unknown | null
          record_id?: string | null
          sensitive_fields?: string[] | null
          table_name?: string
          user_agent?: string | null
          user_id?: string | null
        }
        Relationships: []
      }
      calls: {
        Row: {
          call_type: string
          caller_name_masked: string | null
          caller_phone_masked: string | null
          created_at: string | null
          duration_seconds: number
          hour_of_day: number | null
          id: string
          intent: string | null
          outcome: string
          salon_id: string | null
          sentiment: string | null
          timestamp: string
        }
        Insert: {
          call_type: string
          caller_name_masked?: string | null
          caller_phone_masked?: string | null
          created_at?: string | null
          duration_seconds?: number
          hour_of_day?: number | null
          id?: string
          intent?: string | null
          outcome: string
          salon_id?: string | null
          sentiment?: string | null
          timestamp: string
        }
        Update: {
          call_type?: string
          caller_name_masked?: string | null
          caller_phone_masked?: string | null
          created_at?: string | null
          duration_seconds?: number
          hour_of_day?: number | null
          id?: string
          intent?: string | null
          outcome?: string
          salon_id?: string | null
          sentiment?: string | null
          timestamp?: string
        }
        Relationships: [
          {
            foreignKeyName: "calls_salon_id_fkey"
            columns: ["salon_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          created_at: string | null
          id: string
          phone: string | null
          salon_name: string
          timezone: string | null
          updated_at: string | null
        }
        Insert: {
          created_at?: string | null
          id: string
          phone?: string | null
          salon_name: string
          timezone?: string | null
          updated_at?: string | null
        }
        Update: {
          created_at?: string | null
          id?: string
          phone?: string | null
          salon_name?: string
          timezone?: string | null
          updated_at?: string | null
        }
        Relationships: []
      }
      salon_info: {
        Row: {
          address: string | null
          business_name: string | null
          created_at: string | null
          faq_items: Json | null
          hours: Json | null
          id: string
          phone: string | null
          salon_id: string | null
          scraped_at: string | null
          updated_at: string | null
          website_url: string | null
        }
        Insert: {
          address?: string | null
          business_name?: string | null
          created_at?: string | null
          faq_items?: Json | null
          hours?: Json | null
          id?: string
          phone?: string | null
          salon_id?: string | null
          scraped_at?: string | null
          updated_at?: string | null
          website_url?: string | null
        }
        Update: {
          address?: string | null
          business_name?: string | null
          created_at?: string | null
          faq_items?: Json | null
          hours?: Json | null
          id?: string
          phone?: string | null
          salon_id?: string | null
          scraped_at?: string | null
          updated_at?: string | null
          website_url?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "salon_info_salon_id_fkey"
            columns: ["salon_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      salon_static_data: {
        Row: {
          created_at: string | null
          data: Json
          key: string
          updated_at: string | null
        }
        Insert: {
          created_at?: string | null
          data: Json
          key: string
          updated_at?: string | null
        }
        Update: {
          created_at?: string | null
          data?: Json
          key?: string
          updated_at?: string | null
        }
        Relationships: []
      }
      scraped_professionals: {
        Row: {
          bio: string | null
          certifications: string[] | null
          created_at: string | null
          experience_years: number | null
          id: string
          image_url: string | null
          name: string
          raw_data: Json | null
          salon_id: string | null
          specialties: string[] | null
          title: string | null
          updated_at: string | null
        }
        Insert: {
          bio?: string | null
          certifications?: string[] | null
          created_at?: string | null
          experience_years?: number | null
          id?: string
          image_url?: string | null
          name: string
          raw_data?: Json | null
          salon_id?: string | null
          specialties?: string[] | null
          title?: string | null
          updated_at?: string | null
        }
        Update: {
          bio?: string | null
          certifications?: string[] | null
          created_at?: string | null
          experience_years?: number | null
          id?: string
          image_url?: string | null
          name?: string
          raw_data?: Json | null
          salon_id?: string | null
          specialties?: string[] | null
          title?: string | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "scraped_professionals_salon_id_fkey"
            columns: ["salon_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      scraped_services: {
        Row: {
          category: string | null
          created_at: string | null
          description: string | null
          duration: string | null
          id: string
          price: string | null
          raw_data: Json | null
          salon_id: string | null
          service_name: string
          updated_at: string | null
        }
        Insert: {
          category?: string | null
          created_at?: string | null
          description?: string | null
          duration?: string | null
          id?: string
          price?: string | null
          raw_data?: Json | null
          salon_id?: string | null
          service_name: string
          updated_at?: string | null
        }
        Update: {
          category?: string | null
          created_at?: string | null
          description?: string | null
          duration?: string | null
          id?: string
          price?: string | null
          raw_data?: Json | null
          salon_id?: string | null
          service_name?: string
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "scraped_services_salon_id_fkey"
            columns: ["salon_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      services: {
        Row: {
          average_price_cents: number
          created_at: string | null
          id: string
          is_active: boolean | null
          name: string
          salon_id: string | null
          updated_at: string | null
        }
        Insert: {
          average_price_cents: number
          created_at?: string | null
          id?: string
          is_active?: boolean | null
          name: string
          salon_id?: string | null
          updated_at?: string | null
        }
        Update: {
          average_price_cents?: number
          created_at?: string | null
          id?: string
          is_active?: boolean | null
          name?: string
          salon_id?: string | null
          updated_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "services_salon_id_fkey"
            columns: ["salon_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      user_google_tokens: {
        Row: {
          access_token: string
          created_at: string
          expires_at: string
          id: string
          is_active: boolean
          last_used_at: string | null
          last_used_ip: unknown | null
          refresh_token: string | null
          scope: string | null
          token_version: number
          updated_at: string
          user_id: string
        }
        Insert: {
          access_token: string
          created_at?: string
          expires_at: string
          id?: string
          is_active?: boolean
          last_used_at?: string | null
          last_used_ip?: unknown | null
          refresh_token?: string | null
          scope?: string | null
          token_version?: number
          updated_at?: string
          user_id: string
        }
        Update: {
          access_token?: string
          created_at?: string
          expires_at?: string
          id?: string
          is_active?: boolean
          last_used_at?: string | null
          last_used_ip?: unknown | null
          refresh_token?: string | null
          scope?: string | null
          token_version?: number
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          created_at: string
          id: string
          role: Database["public"]["Enums"]["app_role"]
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      get_all_salons_overview: {
        Args: Record<PropertyKey, never>
        Returns: {
          created_at: string
          phone: string
          salon_id: string
          salon_name: string
          timezone: string
          total_appointments: number
          total_calls: number
          total_revenue_cents: number
        }[]
      }
      get_calls_timeseries: {
        Args: { p_days?: number; p_salon_id: string }
        Returns: {
          after_hours_captured: number
          answered: number
          date: string
          missed: number
        }[]
      }
      get_current_user_role: {
        Args: Record<PropertyKey, never>
        Returns: Database["public"]["Enums"]["app_role"]
      }
      get_platform_metrics: {
        Args: Record<PropertyKey, never>
        Returns: {
          active_salons: number
          total_appointments: number
          total_calls: number
          total_revenue_cents: number
          total_salons: number
        }[]
      }
      get_profile_safe: {
        Args: { profile_id: string }
        Returns: {
          created_at: string
          id: string
          phone: string
          salon_name: string
          timezone: string
        }[]
      }
      get_recent_calls_view: {
        Args: Record<PropertyKey, never>
        Returns: {
          caller_name_masked: string
          duration_seconds: number
          id: string
          intent: string
          outcome: string
          salon_id: string
          sentiment: string
          timestamp: string
        }[]
      }
      get_revenue_by_service_view: {
        Args: Record<PropertyKey, never>
        Returns: {
          appointment_count: number
          revenue_cents: number
          salon_id: string
          service: string
        }[]
      }
      get_salon_kpis: {
        Args: { p_days?: number; p_salon_id: string }
        Returns: {
          appointments_booked: number
          calls_answered: number
          conversion_rate: number
          revenue_recovered_cents: number
        }[]
      }
      get_salons_basic_info: {
        Args: Record<PropertyKey, never>
        Returns: {
          created_at: string
          salon_id: string
          salon_name: string
          timezone: string
          total_appointments: number
          total_calls: number
          total_revenue_cents: number
        }[]
      }
      get_user_google_token: {
        Args: { requesting_user_id: string }
        Returns: {
          access_token: string
          expires_at: string
          refresh_token: string
          scope: string
        }[]
      }
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
      log_sensitive_access: {
        Args: {
          p_action: string
          p_record_id?: string
          p_sensitive_fields?: string[]
          p_table_name: string
        }
        Returns: undefined
      }
      mask_phone_number: {
        Args: { phone_number: string }
        Returns: string
      }
      revoke_user_google_tokens: {
        Args: { requesting_user_id: string }
        Returns: boolean
      }
      store_user_google_token: {
        Args: {
          new_access_token: string
          new_expires_at: string
          new_refresh_token: string
          new_scope: string
          requesting_user_id: string
        }
        Returns: boolean
      }
    }
    Enums: {
      app_role: "admin" | "salon_owner"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["admin", "salon_owner"],
    },
  },
} as const
