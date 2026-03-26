"use client";
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Heading,
  Text,
  Link as ChakraLink,
  useToast,
  FormErrorMessage,
} from "@chakra-ui/react";
import NextLink from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/hooks/useAuth";
import { ApiError } from "@/lib/api/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const router = useRouter();
  const toast = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) setError("Invalid email or password");
      else toast({ title: "Network error", status: "error" });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Box maxW="400px" mx="auto" mt={20} p={8}>
      <Heading size="lg" mb={6}>
        Log In
      </Heading>
      <form onSubmit={handleSubmit}>
        <VStack spacing={4}>
          <FormControl isRequired isInvalid={!!error}>
            <FormLabel htmlFor="email">Email</FormLabel>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </FormControl>
          <FormControl isRequired isInvalid={!!error}>
            <FormLabel htmlFor="password">Password</FormLabel>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && <FormErrorMessage>{error}</FormErrorMessage>}
          </FormControl>
          <Button
            type="submit"
            colorScheme="blue"
            w="full"
            isLoading={isSubmitting}
          >
            Log In
          </Button>
        </VStack>
      </form>
      <Text mt={4} fontSize="sm" textAlign="center">
        Don&apos;t have an account?{" "}
        <ChakraLink as={NextLink} href="/signup" color="blue.500">
          Sign up
        </ChakraLink>
      </Text>
    </Box>
  );
}
