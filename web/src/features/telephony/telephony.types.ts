import type { components } from "@/api/generated/schema";
import type { FilterGroup } from "@/lib/filters";

type PhoneNumber = components["schemas"]["PhoneNumberApiResponseSchema"];
type PhoneNumberCreate = components["schemas"]["PhoneNumberCreateSchema"];
type PhoneNumberUpdate = components["schemas"]["PhoneNumberUpdateSchema"];
type PhoneNumberStatus = components["schemas"]["PhoneNumberStatus"];
type TelephonyCall = components["schemas"]["TelephonyCallApiResponseSchema"];
type TelephonyConfig = components["schemas"]["ProviderConfigApiResponseSchema"];
type TelephonyAgent = components["schemas"]["AgentResponseSchema"];
type AvailableNumber = components["schemas"]["AvailableNumberSchema"];
type NumberType = components["schemas"]["NumberType"];
type NumberPurchase = components["schemas"]["NumberPurchaseRequest"];
type DeletionJob = components["schemas"]["DeletionJobApiResponse"];

type PhoneNumberFilterProperty = "provider" | "status";
type PhoneNumberSortField = "label" | "number" | "status" | "updated_at";
type CallFilterProperty = "direction" | "provider" | "status";
type CallSortField = "duration" | "provider" | "started_at" | "status";
type TelephonySortDirection = "asc" | "desc";

interface PhoneNumberCollectionQuery {
  direction: TelephonySortDirection;
  filters: FilterGroup<PhoneNumberFilterProperty>;
  search: string;
  sortBy: PhoneNumberSortField;
}

interface CallCollectionQuery {
  direction: TelephonySortDirection;
  filters: FilterGroup<CallFilterProperty>;
  search: string;
  sortBy: CallSortField;
}

interface AvailableNumberSearch {
  areaCode?: string;
  contains?: string;
  country: string;
  limit: number;
  numberType: NumberType;
}

export type {
  AvailableNumber,
  AvailableNumberSearch,
  CallCollectionQuery,
  CallFilterProperty,
  CallSortField,
  DeletionJob,
  NumberPurchase,
  NumberType,
  PhoneNumber,
  PhoneNumberCollectionQuery,
  PhoneNumberCreate,
  PhoneNumberFilterProperty,
  PhoneNumberSortField,
  PhoneNumberStatus,
  PhoneNumberUpdate,
  TelephonyAgent,
  TelephonyCall,
  TelephonyConfig,
  TelephonySortDirection,
};
