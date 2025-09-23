import { Button } from "@/components/ui/button";
import { Phone, Mail, MapPin } from "lucide-react";

export const Footer = () => {
  return (
    <footer className="bg-foreground text-background py-16">
      <div className="container mx-auto px-4">
        <div className="grid md:grid-cols-4 gap-8 mb-12">
          {/* Brand */}
          <div className="md:col-span-2">
            <h3 className="text-2xl font-bold mb-4">DispatchOne</h3>
            <p className="text-background/80 mb-6 max-w-md leading-relaxed">
              Transform your customer service with AI-powered dispatch that never sleeps. 
              Turn every call into a customer, 24/7.
            </p>
            <Button variant="outline" className="border-background/20 text-background hover:bg-background hover:text-foreground">
              Start Free Trial
            </Button>
          </div>

          {/* Quick Links */}
          <div>
            <h4 className="font-semibold mb-4">Quick Links</h4>
            <ul className="space-y-2 text-background/80">
              <li><a href="#" className="hover:text-background transition-colors">How It Works</a></li>
              <li><a href="#" className="hover:text-background transition-colors">Pricing</a></li>
              <li><a href="#" className="hover:text-background transition-colors">Case Studies</a></li>
              <li><a href="#" className="hover:text-background transition-colors">Support</a></li>
              <li><a href="#" className="hover:text-background transition-colors">API Docs</a></li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h4 className="font-semibold mb-4">Contact</h4>
            <div className="space-y-3 text-background/80">
              <div className="flex items-center gap-2">
                <Phone className="h-4 w-4" />
                <span>1-800-DISPATCH</span>
              </div>
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4" />
                <span>hello@dispatchone.ai</span>
              </div>
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4" />
                <span>San Francisco, CA</span>
              </div>
            </div>
          </div>
        </div>

        <div className="border-t border-background/20 pt-8 flex flex-col md:flex-row justify-between items-center">
          <div className="text-background/60 text-sm mb-4 md:mb-0">
            © 2024 DispatchOne. All rights reserved.
          </div>
          <div className="flex gap-6 text-background/60 text-sm">
            <a href="#" className="hover:text-background transition-colors">Privacy Policy</a>
            <a href="#" className="hover:text-background transition-colors">Terms of Service</a>
            <a href="#" className="hover:text-background transition-colors">Security</a>
          </div>
        </div>
      </div>
    </footer>
  );
};