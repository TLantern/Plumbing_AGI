import { CheckCircle, Clock, TrendingUp } from "lucide-react";

const benefits = [
  {
    icon: Clock,
    title: "Reduced Missed Calls",
    description: "Never lose another customer to voicemail. Our AI answers every call within 2 rings, 24/7.",
    stat: "95% fewer missed calls"
  },
  {
    icon: TrendingUp,
    title: "Higher Booking Rates",
    description: "Convert more callers into appointments with intelligent scheduling and availability optimization.",
    stat: "40% increase in bookings"
  },
  {
    icon: CheckCircle,
    title: "Lower Overhead",
    description: "Eliminate the need for dedicated reception staff while providing better service than human operators.",
    stat: "60% cost reduction"
  }
];

export const Benefits = () => {
  return (
    <section className="py-16 lg:py-24 bg-background">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Why Choose DispatchOne?
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Transform your business operations with AI-powered call management that delivers real results.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {benefits.map((benefit, index) => (
            <div
              key={index}
              className="text-center p-6 rounded-xl bg-card border border-border shadow-soft hover:shadow-card transition-all duration-300 group"
            >
              <div className="mb-6">
                <div className="w-16 h-16 mx-auto rounded-full bg-gradient-hero flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                  <benefit.icon className="h-8 w-8 text-primary-foreground" />
                </div>
              </div>
              
              <h3 className="text-xl font-semibold mb-3">{benefit.title}</h3>
              <p className="text-muted-foreground mb-4 leading-relaxed">
                {benefit.description}
              </p>
              
              <div className="text-2xl font-bold text-primary">{benefit.stat}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};