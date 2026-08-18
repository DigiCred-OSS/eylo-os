import type { components } from "@/api/generated/schema";

type LoginCredentials = components["schemas"]["LoginRequestSchema"];
type Member = components["schemas"]["MemberApiResponseSchema"];

export type { LoginCredentials, Member };
