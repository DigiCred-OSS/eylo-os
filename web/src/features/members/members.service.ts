import type { ApiClient } from "@/api/client";
import { toMemberListApiQuery } from "@/features/members/members.query";
import type {
  Member,
  MemberCollectionQuery,
  MembersPage,
} from "@/features/members/members.types";

class MembersService {
  private readonly api: ApiClient;

  constructor(api: ApiClient) {
    this.api = api;
  }

  async listMembers(
    organizationId: string,
    query: MemberCollectionQuery,
    signal?: AbortSignal,
  ): Promise<MembersPage> {
    return requireData(
      await this.api.GET("/api/{organization_id}/members", {
        params: {
          path: { organization_id: organizationId },
          query: toMemberListApiQuery(query),
        },
        signal,
      }),
      "Members could not be loaded.",
    );
  }

  async getMember(
    organizationId: string,
    memberId: string,
    signal?: AbortSignal,
  ): Promise<Member> {
    return requireData(
      await this.api.GET("/api/{organization_id}/members/{member_id}", {
        params: {
          path: { member_id: memberId, organization_id: organizationId },
        },
        signal,
      }),
      "This member could not be loaded.",
    );
  }
}

function requireData<Data>(
  result: { data?: Data; response: Response },
  message: string,
): Data {
  if (!result.response.ok || result.data === undefined)
    throw new Error(message);
  return result.data;
}

export { MembersService };
