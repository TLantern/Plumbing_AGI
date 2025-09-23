import Autoplay from "embla-carousel-autoplay";
import { Carousel, CarouselContent, CarouselItem } from "@/components/ui/carousel";

const companyLogos = [
  { name: "WordPress", url: "https://s.w.org/style/images/about/WordPress-logotype-wmark.png" },
  { name: "Google", url: "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png" },
  { name: "Yelp", url: "https://logos-world.net/wp-content/uploads/2020/11/Yelp-Logo.png" },
  { name: "LinkedIn", url: "https://content.linkedin.com/content/dam/me/business/en-us/amp/brand-site/v2/bg/LI-Bug.svg.original.svg" },
  { name: "Starbucks", url: "https://logos-world.net/wp-content/uploads/2020/09/Starbucks-Logo.png" },
  { name: "Microsoft", url: "https://img-prod-cms-rt-microsoft-com.akamaized.net/cms/api/am/imageFileData/RE1Mu3b?ver=5c31" },
  { name: "Amazon", url: "https://logos-world.net/wp-content/uploads/2020/04/Amazon-Logo.png" },
  { name: "Apple", url: "https://logos-world.net/wp-content/uploads/2020/04/Apple-Logo.png" },
  { name: "Meta", url: "https://logos-world.net/wp-content/uploads/2021/10/Meta-Logo.png" },
  { name: "Tesla", url: "https://logos-world.net/wp-content/uploads/2021/03/Tesla-Logo.png" },
  { name: "Netflix", url: "https://logos-world.net/wp-content/uploads/2020/04/Netflix-Logo.png" },
  { name: "Adobe", url: "https://logos-world.net/wp-content/uploads/2020/11/Adobe-Logo.png" }
];

export const TrustedByCarousel = () => {
  return (
    <div className="mt-16 max-w-4xl mx-auto">
      <Carousel
        opts={{
          align: "start",
          loop: true,
        }}
        plugins={[
          Autoplay({
            delay: 2500,
          }),
        ]}
        className="w-full"
      >
        <CarouselContent className="-ml-2 md:-ml-4">
          {companyLogos.map((company, index) => (
            <CarouselItem key={index} className="pl-2 md:pl-4 basis-1/2 md:basis-1/3 lg:basis-1/4">
              <div className="flex items-center justify-center h-16 px-4 bg-background/60 backdrop-blur-sm rounded-lg border border-border/20">
                <img
                  src={company.url}
                  alt={`${company.name} logo`}
                  className="max-h-8 max-w-full object-contain opacity-70 hover:opacity-100 transition-opacity"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                />
              </div>
            </CarouselItem>
          ))}
        </CarouselContent>
      </Carousel>
    </div>
  );
};