import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Shield, ShieldCheck, ShieldX, AlertTriangle, RefreshCw } from 'lucide-react';
import { supabase } from '@/integrations/supabase/client';
import { useToast } from '@/hooks/use-toast';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';

interface GoogleCalendarSecurityProps {
  isConnected: boolean;
  onConnectionChange: () => void;
}

export const GoogleCalendarSecurity = ({ isConnected, onConnectionChange }: GoogleCalendarSecurityProps) => {
  const [revoking, setRevoking] = useState(false);
  const { toast } = useToast();

  const revokeTokens = async () => {
    try {
      setRevoking(true);
      const session = await supabase.auth.getSession();
      if (!session.data.session) return;

      const { error } = await supabase.rpc('revoke_user_google_tokens', {
        requesting_user_id: session.data.session.user.id
      });

      if (error) throw error;

      toast({
        title: "Access Revoked",
        description: "Google Calendar access has been successfully revoked.",
      });

      onConnectionChange();
    } catch (error) {
      console.error('Error revoking tokens:', error);
      toast({
        title: "Revocation Failed",
        description: "Failed to revoke Google Calendar access. Please try again.",
        variant: "destructive",
      });
    } finally {
      setRevoking(false);
    }
  };

  return (
    <Card className="border-l-4 border-l-blue-500">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Shield className="h-4 w-4" />
          OAuth Security Status
        </CardTitle>
        <CardDescription className="text-xs">
          Manage your Google Calendar integration security
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isConnected ? (
              <>
                <ShieldCheck className="h-4 w-4 text-green-600" />
                <span className="text-sm font-medium">Connected</span>
              </>
            ) : (
              <>
                <ShieldX className="h-4 w-4 text-gray-400" />
                <span className="text-sm font-medium text-muted-foreground">Not Connected</span>
              </>
            )}
          </div>
          {isConnected ? (
            <Badge variant="outline" className="text-green-600 border-green-600 bg-green-50">
              Active
            </Badge>
          ) : (
            <Badge variant="outline" className="text-gray-400 border-gray-400">
              Inactive
            </Badge>
          )}
        </div>

        {isConnected && (
          <>
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <ShieldCheck className="h-3 w-3" />
                <span>Tokens stored with enhanced security</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <RefreshCw className="h-3 w-3" />
                <span>Automatic token refresh enabled</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Shield className="h-3 w-3" />
                <span>Access tracked with IP and timestamps</span>
              </div>
            </div>

            <div className="border-t pt-4">
              <div className="flex items-start gap-2 mb-3">
                <AlertTriangle className="h-4 w-4 text-orange-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs font-medium text-orange-800">Security Recommendation</p>
                  <p className="text-xs text-orange-700 mt-1">
                    Regularly review and revoke unused access tokens. If you suspect unauthorized access, 
                    revoke tokens immediately.
                  </p>
                </div>
              </div>

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="w-full text-red-600 border-red-200 hover:bg-red-50"
                  >
                    <ShieldX className="h-3 w-3 mr-2" />
                    Revoke Google Access
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Revoke Google Calendar Access?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will permanently revoke all Google OAuth tokens and disconnect your calendar. 
                      You'll need to reconnect to access your calendar again. This action cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction 
                      onClick={revokeTokens} 
                      disabled={revoking}
                      className="bg-red-600 hover:bg-red-700"
                    >
                      {revoking ? (
                        <>
                          <div className="animate-spin rounded-full h-3 w-3 border-b border-white mr-2"></div>
                          Revoking...
                        </>
                      ) : (
                        'Revoke Access'
                      )}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </>
        )}

        {!isConnected && (
          <div className="text-xs text-muted-foreground bg-gray-50 p-3 rounded-lg">
            <p className="font-medium mb-1">Security Features When Connected:</p>
            <ul className="space-y-1 text-xs">
              <li>• Encrypted token storage</li>
              <li>• Automatic token rotation</li>
              <li>• Access logging and monitoring</li>
              <li>• One-click revocation</li>
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
};