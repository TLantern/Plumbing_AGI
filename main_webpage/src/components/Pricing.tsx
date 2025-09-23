import { Button } from "@/components/ui/button";
import { Check, Zap, Crown, Building } from "lucide-react";

const plans = [
  {
    name: "Starter",
    icon: Zap,
    price: 129,
    description: "Perfect for small businesses getting started",
    features: [
      "Up to 100 calls per month",
      "Basic appointment scheduling",
      "Email notifications",
      "Standard business hours support",
      "1 phone number integration"
    ],
    popular: false
  },
  {
    name: "Professional", 
    icon: Crown,
    price: 399,
    description: "Most popular for growing businesses",
    features: [
      "Up to 500 calls per month",
      "Advanced AI conversation",
      "SMS & email notifications",
      "24/7 availability",
      "3 phone number integrations",
      "Custom scheduling rules",
      "Analytics dashboard"
    ],
    popular: true
  },
  {
    name: "Enterprise",
    icon: Building,
    price: "Custom",
    description: "Tailored solutions for large operations",
    features: [
      "Unlimited calls",
      "Multi-location support",
      "Custom AI training",
      "Priority support",
      "Unlimited integrations",
      "Advanced analytics",
      "Custom API access",
      "Dedicated account manager"
    ],
    popular: false
  }
];

export const Pricing = () => {
  return (
    <section className="py-16 lg:py-24 bg-gradient-subtle">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Simple, Transparent Pricing
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Choose the perfect plan for your business. All plans include our core AI dispatch features.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {plans.map((plan, index) => (
            <div
              key={index}
              className={`relative bg-card border rounded-xl p-6 shadow-soft hover:shadow-card transition-all duration-300 ${
                plan.popular ? 'border-primary scale-105 shadow-button' : 'border-border'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                  <span className="bg-gradient-hero text-primary-foreground px-3 py-1 rounded-full text-sm font-medium">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="text-center mb-6">
                <div className="mb-4">
                  <div className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center ${
                    plan.popular ? 'bg-gradient-hero' : 'bg-secondary'
                  }`}>
                    <plan.icon className={`h-8 w-8 ${
                      plan.popular ? 'text-primary-foreground' : 'text-secondary-foreground'
                    }`} />
                  </div>
                </div>
                
                <h3 className="text-xl font-semibold mb-2">{plan.name}</h3>
                <p className="text-muted-foreground text-sm mb-4">{plan.description}</p>
                
                <div className="mb-6">
                  {typeof plan.price === 'number' ? (
                    <div>
                      <span className="text-3xl font-bold">${plan.price}</span>
                      <span className="text-muted-foreground">/month</span>
                    </div>
                  ) : (
                    <span className="text-3xl font-bold">{plan.price}</span>
                  )}
                </div>
              </div>

              <ul className="space-y-3 mb-8">
                {plan.features.map((feature, featureIndex) => (
                  <li key={featureIndex} className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary flex-shrink-0" />
                    <span className="text-sm text-muted-foreground">{feature}</span>
                  </li>
                ))}
              </ul>

              <Button 
                variant={plan.popular ? "hero" : "secondary"} 
                className="w-full"
                size="lg"
              >
                {plan.name === "Enterprise" ? "Contact Sales" : "Get Started"}
              </Button>
            </div>
          ))}
        </div>

        <div className="text-center mt-12">
          <p className="text-muted-foreground mb-4">
            All plans include a 14-day free trial. No setup fees. Cancel anytime.
          </p>
          <Button variant="outline">
            Compare All Features
          </Button>
        </div>
      </div>
    </section>
  );
};