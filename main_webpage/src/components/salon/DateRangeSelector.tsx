import { Button } from "@/components/ui/button";
import { Calendar } from "lucide-react";
import type { DateRange } from "@/types/salon";

interface DateRangeSelectorProps {
  selectedRange: DateRange;
  onRangeChange: (range: DateRange) => void;
}

export function DateRangeSelector({ selectedRange, onRangeChange }: DateRangeSelectorProps) {
  const ranges: { value: DateRange; label: string }[] = [
    { value: "7", label: "7 days" },
    { value: "30", label: "30 days" },
    { value: "90", label: "90 days" },
  ];

  return (
    <div className="flex items-center gap-2">
      <Calendar className="h-4 w-4 text-muted-foreground" />
      <div className="flex rounded-lg border bg-muted/50 p-1">
        {ranges.map((range) => (
          <Button
            key={range.value}
            variant={selectedRange === range.value ? "default" : "ghost"}
            size="sm"
            onClick={() => onRangeChange(range.value)}
            className={
              selectedRange === range.value
                ? "bg-primary text-primary-foreground shadow-sm"
                : "hover:bg-transparent hover:text-foreground"
            }
          >
            {range.label}
          </Button>
        ))}
      </div>
    </div>
  );
}