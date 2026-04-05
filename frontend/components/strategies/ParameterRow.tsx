"use client";
import {
  Box,
  Button,
  ButtonGroup,
  Grid,
  Input,
  NumberInput,
  NumberInputField,
  Select,
  Text,
  useColorModeValue,
} from "@chakra-ui/react";

export interface ParameterRowProps {
  label: string;
  fieldKey: string;
  required?: boolean;
  source: "fixed" | "signal";
  fixedValue: string | number | null;
  signalField: string;
  inputType: "text" | "number" | "select";
  selectOptions?: { value: string; label: string }[];
  showPriceError?: boolean;
  onSourceChange: (source: "fixed" | "signal") => void;
  onFixedChange: (value: string | number) => void;
  onSignalFieldChange: (fieldName: string) => void;
  customFixedInput?: React.ReactNode;
}

export function ParameterRow({
  label,
  fieldKey,
  required,
  source,
  fixedValue,
  signalField,
  inputType,
  selectOptions,
  showPriceError,
  onSourceChange,
  onFixedChange,
  onSignalFieldChange,
  customFixedInput,
}: ParameterRowProps) {
  const labelColor = useColorModeValue("gray.700", "gray.300");
  const reqColor = useColorModeValue("red.500", "red.400");

  return (
    <Grid
      templateColumns={{ base: "1fr", md: "160px 200px 1fr" }}
      gap={3}
      alignItems="center"
      data-testid={`param-row-${fieldKey}`}
    >
      {/* Label */}
      <Text fontSize="sm" color={labelColor} fontWeight="medium">
        {label}
        {required && (
          <Text as="span" color={reqColor} ml={1} fontSize="xs">
            *
          </Text>
        )}
      </Text>

      {/* Source toggle */}
      <ButtonGroup size="sm" isAttached variant="outline">
        <Button
          colorScheme={source === "fixed" ? "green" : "gray"}
          variant={source === "fixed" ? "solid" : "outline"}
          onClick={() => onSourceChange("fixed")}
          data-testid={`${fieldKey}-fixed-btn`}
        >
          Fixed
        </Button>
        <Button
          colorScheme={source === "signal" ? "orange" : "gray"}
          variant={source === "signal" ? "solid" : "outline"}
          onClick={() => onSourceChange("signal")}
          data-testid={`${fieldKey}-signal-btn`}
        >
          From signal
        </Button>
      </ButtonGroup>

      {/* Value input */}
      <Box>
        {source === "fixed" ? (
          customFixedInput ? (
            customFixedInput
          ) : inputType === "select" && selectOptions ? (
            <Select
              size="sm"
              value={String(fixedValue ?? "")}
              onChange={(e) => onFixedChange(e.target.value)}
              data-testid={`${fieldKey}-select`}
            >
              {selectOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          ) : inputType === "number" ? (
            <NumberInput
              size="sm"
              value={fixedValue as number ?? 0}
              onChange={(_, valAsNumber) =>
                onFixedChange(isNaN(valAsNumber) ? 0 : valAsNumber)
              }
              min={0}
            >
              <NumberInputField data-testid={`${fieldKey}-number-input`} />
            </NumberInput>
          ) : (
            <Input
              size="sm"
              value={String(fixedValue ?? "")}
              onChange={(e) => onFixedChange(e.target.value)}
              data-testid={`${fieldKey}-text-input`}
            />
          )
        ) : (
          <Box>
            <Input
              size="sm"
              placeholder="field name in signal"
              value={signalField}
              onChange={(e) => onSignalFieldChange(e.target.value)}
              data-testid={`${fieldKey}-signal-input`}
            />
            {showPriceError && (
              <Text color="red.400" fontSize="xs" role="alert" mt={1}>
                Required when order type is LIMIT
              </Text>
            )}
          </Box>
        )}
        {source === "fixed" && showPriceError && (
          <Text color="red.400" fontSize="xs" role="alert" mt={1}>
            Required when order type is LIMIT
          </Text>
        )}
      </Box>
    </Grid>
  );
}
