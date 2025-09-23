import { Phone, Bot, Calendar } from "lucide-react";

const steps = [
  {
    icon: Phone,
    title: "Call Comes In",
    description: "Customer calls your business number during any hour of the day or night."
  },
  {
    icon: Bot,
    title: "AI Picks Up",
    description: "Our intelligent system answers instantly and engages in natural conversation with your caller."
  },
  {
    icon: Calendar,
    title: "Appointment Booked",
    description: "AI schedules the appointment directly in your calendar and sends confirmations to both parties."
  }
];

export const HowItWorks = () => {
  return (
    <section className="py-16 lg:py-24 bg-gradient-subtle">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            How It Works
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Three simple steps to transform your customer service and never miss an opportunity.
          </p>
        </div>

        <div className="max-w-4xl mx-auto">
          <div className="grid md:grid-cols-3 gap-8 md:gap-4">
            {steps.map((step, index) => (
              <div key={index} className="relative">
                <div className="text-center p-6">
                  <div className="mb-6">
                    <div className="w-20 h-20 mx-auto rounded-full bg-primary flex items-center justify-center shadow-button">
                      <step.icon className="h-10 w-10 text-primary-foreground" />
                    </div>
                    <div className="absolute top-16 left-1/2 transform -translate-x-1/2 w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold shadow-soft">
                      {index + 1}
                    </div>
                  </div>
                  
                  <h3 className="text-xl font-semibold mb-3">{step.title}</h3>
                  <p className="text-muted-foreground leading-relaxed">
                    {step.description}
                  </p>
                </div>

                {/* Arrow connector for desktop */}
                {index < steps.length - 1 && (
                  <div className="hidden md:block absolute top-10 -right-4 w-8 h-8">
                    <svg className="w-full h-full text-primary" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M12.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};