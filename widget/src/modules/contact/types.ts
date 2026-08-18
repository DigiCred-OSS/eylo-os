export type TContact = {
  id: string;
  externalId?: string;
  name?: string;
  primaryEmail?: string;
  primaryPhone?: string;
  preferences?: Record<string, string>;
};

export type TContactCreate = Omit<TContact, "id"> & {
  id?: string;
};
