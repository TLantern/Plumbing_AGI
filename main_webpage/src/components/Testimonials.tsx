import { Star, Quote } from "lucide-react";

const testimonials = [
  {
    name: "Sarah Chen",
    title: "Dental Practice Owner",
    company: "Bright Smile Dentistry",
    content: "DispatchOne transformed our practice. We went from missing 3-4 calls daily to capturing every opportunity. Our booking rate increased by 45% in just two months.",
    rating: 5,
    avatar: "SC"
  },
  {
    name: "Michael Rodriguez",
    title: "HVAC Business Owner", 
    company: "Rodriguez Heating & Cooling",
    content: "The AI dispatcher handles emergency calls better than our old answering service. Customers love getting instant responses, even at 2 AM.",
    rating: 5,
    avatar: "MR"
  },
  {
    name: "Jennifer Park",
    title: "Spa Director",
    company: "Zen Wellness Spa",
    content: "Our staff can now focus on clients instead of constantly answering phones. The system books appointments seamlessly and handles rescheduling like a pro.",
    rating: 5,
    avatar: "JP"
  }
];

export const Testimonials = () => {
  return (
    <section className="py-16 lg:py-24 bg-background">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Trusted by Growing Businesses
          </h2>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            See how DispatchOne is helping businesses like yours capture more opportunities and delight customers.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {testimonials.map((testimonial, index) => (
            <div
              key={index}
              className="bg-card border border-border rounded-xl p-6 shadow-soft hover:shadow-card transition-all duration-300 relative"
            >
              <Quote className="absolute top-4 right-4 h-8 w-8 text-primary opacity-20" />
              
              <div className="mb-4">
                <div className="flex items-center gap-1 mb-3">
                  {[...Array(testimonial.rating)].map((_, i) => (
                    <Star key={i} className="h-4 w-4 fill-primary text-primary" />
                  ))}
                </div>
                <p className="text-muted-foreground leading-relaxed italic">
                  "{testimonial.content}"
                </p>
              </div>

              <div className="flex items-center gap-3 pt-4 border-t border-border">
                <div className="w-12 h-12 rounded-full bg-gradient-hero flex items-center justify-center">
                  <span className="text-primary-foreground font-semibold text-sm">
                    {testimonial.avatar}
                  </span>
                </div>
                <div>
                  <div className="font-semibold text-sm">{testimonial.name}</div>
                  <div className="text-xs text-muted-foreground">{testimonial.title}</div>
                  <div className="text-xs text-primary font-medium">{testimonial.company}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};