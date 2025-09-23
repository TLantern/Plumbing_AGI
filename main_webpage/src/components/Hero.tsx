import { Button } from "@/components/ui/button";
import { ArrowRight, Phone } from "lucide-react";
import { TrustedByCarousel } from "./TrustedByCarousel";

export const Hero = () => {
  return (
    <section className="relative bg-gradient-subtle min-h-screen flex items-center pt-16">
      <div className="container mx-auto px-4 py-16 lg:py-24">
        <div className="max-w-4xl mx-auto space-y-12">
          <div className="text-center space-y-8">
            <div className="space-y-4">
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight">
                Turn every call into a{" "}
                <span className="text-primary bg-gradient-hero bg-clip-text text-transparent">
                  customer
                </span>
              </h1>
              <p className="text-xl md:text-2xl text-muted-foreground font-medium">
                DispatchOne books every appointment, 24/7.
              </p>
            </div>
            
            <p className="text-lg text-muted-foreground max-w-lg leading-relaxed mx-auto">
              Save time and money with our AI dispatch system that automatically picks up calls 
              and books appointments around the clock. Never miss another opportunity.
            </p>

            <div className="flex justify-center">
              <Button variant="hero" size="lg" className="group px-12 py-4 bg-gradient-hero text-primary-foreground shadow-button">
                Book a Demo
                <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
              </Button>
            </div>

            <div className="flex items-center gap-8 pt-4 justify-center">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-primary rounded-full"></div>
                <span className="text-sm text-muted-foreground">24/7 Availability</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-primary rounded-full"></div>
                <span className="text-sm text-muted-foreground">Instant Setup</span>
              </div>
            </div>
          </div>

          <div className="relative max-w-3xl mx-auto">
            <div className="relative z-10 rounded-2xl overflow-hidden shadow-card">
              <img
                src="/lovable-uploads/b15abd0e-0734-48f3-9332-e49d3b1b778b.png"
                alt="Virtual agent appointment booking confirmation message"
                className="w-full h-auto"
              />
            </div>
            <div className="absolute inset-0 bg-gradient-hero opacity-10 rounded-2xl"></div>
          </div>
        </div>
        
        <TrustedByCarousel />
      </div>
    </section>
  );
};